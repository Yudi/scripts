import asyncio
import csv
import re
import subprocess
from pathlib import Path
from playwright.async_api import async_playwright
import dateparser

# Configuration
CSV_FILE = Path("./zoom_recordings.csv")
OUTPUT_DIR = Path("./zoom_downloads")
FIREFOX_PROFILE_DIR = Path("./firefox_profile")


def sanitize_filename(name: str) -> str:
    """Remove or replace characters that are invalid in filenames."""
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', name)
    sanitized = sanitized.strip('. ')
    return sanitized[:200] if len(sanitized) > 200 else sanitized


def parse_portuguese_date(date_str: str) -> str:
    """Parse Portuguese date format (e.g., '10/fev') and return as 2025-MM-DD."""
    parsed = dateparser.parse(date_str, languages=['pt'], settings={
        'PREFER_DAY_OF_MONTH': 'first',
        'PREFER_DATES_FROM': 'past',
        'DEFAULT_LANGUAGES': ['pt']
    })
    if parsed:
        return parsed.strftime('2025-%m-%d')
    return date_str  # Return original if parsing fails


def load_recordings_from_csv(csv_path: Path) -> list[dict]:
    """Load recording data from CSV file.
    
    Expected format (semicolon-separated):
    Disciplina;Semestre;Data;Professor;Frente;Conteúdo / Link da aula;Link
    """
    recordings = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        
        # Skip header row
        header = next(reader)
        
        for row in reader:
            if len(row) >= 7 and row[6].strip():  # Must have URL in column 7
                date_formatted = parse_portuguese_date(row[2].strip())
                recordings.append({
                    'disciplina': row[0].strip(),
                    'semestre': row[1].strip(),
                    'date': date_formatted,
                    'professor': row[3].strip(),
                    'frente': row[4].strip(),
                    'title': row[5].strip(),
                    'url': row[6].strip()
                })
    
    return recordings


def build_filename(info: dict, side: str) -> str:
    """Build filename from recording info.
    
    Format: {semestre} - {disciplina} - {frente} - {date} - {title} - {side}.mp4
    """
    name = f"{info['semestre']} - {info['disciplina']} - {info['frente']} - {info['date']} - {info['title']} - {side}.mp4"
    return sanitize_filename(name.replace('.mp4', '')) + '.mp4'


def get_stream_type(url: str) -> str:
    """Determine stream type from URL."""
    url_lower = url.lower()
    if '_as_' in url_lower:
        return 'screen'
    elif '_avo_' in url_lower:
        return 'camera'
    elif '_gallery_' in url_lower:
        return 'gallery'
    return 'unknown'


def download_with_curl(video_url: str, output_path: Path, cookies: list[dict], referer: str) -> bool:
    """Download video using curl matching the working command exactly."""
    if output_path.exists() and output_path.stat().st_size > 100000:
        print(f"    Already exists: {output_path.name}")
        return True
    
    # Build cookie string exactly like the working curl: "name1=value1; name2=value2; ..."
    cookie_parts = []
    for c in cookies:
        name = c.get('name', '')
        value = c.get('value', '')
        if name and value:
            cookie_parts.append(f"{name}={value}")
    cookie_string = '; '.join(cookie_parts)
    
    # Build curl command matching the working example EXACTLY
    cmd = [
        'curl',
        video_url,
        '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:142.0) Gecko/20100101 Firefox/142.0',
        '-H', 'Accept: video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5',
        '-H', 'Accept-Language: en-US,en;q=0.8,pt-BR;q=0.5,pt;q=0.3',
        '-H', f'Referer: {referer}',
        '-H', 'DNT: 1',
        '-H', 'Sec-GPC: 1',
        '-H', 'Connection: keep-alive',
        '-H', f'Cookie: {cookie_string}',
        '-H', 'Sec-Fetch-Dest: video',
        '-H', 'Sec-Fetch-Mode: no-cors',
        '-H', 'Sec-Fetch-Site: same-site',
        '-H', 'Accept-Encoding: identity',
        '-H', 'Priority: u=4',
        '--compressed',
        '--output', str(output_path),
    ]
    
    try:
        print(f"    Downloading with curl...")
        print(f"    URL: {video_url[:100]}...")
        print(f"    Cookie header length: {len(cookie_string)} chars")
        
        # Run curl
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"    curl failed with code {result.returncode}")
            if result.stderr:
                print(f"    stderr: {result.stderr[:500]}")
            return False
        
        if output_path.exists():
            size_mb = output_path.stat().st_size / 1024 / 1024
            if size_mb > 0.5:
                print(f"    ✓ Saved: {output_path.name} ({size_mb:.1f} MB)")
                return True
            else:
                print(f"    Download too small ({size_mb:.2f} MB)")
                # Check content
                try:
                    with open(output_path, 'rb') as f:
                        content = f.read(500)
                        print(f"    Content: {content[:200]}")
                except:
                    pass
                output_path.unlink(missing_ok=True)
                return False
        else:
            print(f"    No output file created")
            return False
            
    except Exception as e:
        print(f"    curl error: {e}")
        return False


async def process_recording(context, recording: dict, index: int, total: int) -> dict:
    """Process a single Zoom recording - capture signed URLs and download.
    
    Returns dict with status: 'success', 'partial', 'failed', or 'skipped'
    """
    
    title = recording['title']
    url = recording['url']
    
    # Build display name for logging
    display_name = f"{recording['disciplina']} - {recording['frente']} - {title}"
    
    result = {
        'recording': recording,
        'title': title,
        'url': url,
        'status': 'failed',
        'streams_downloaded': [],
        'streams_failed': [],
        'error': None
    }
    
    print(f"\n[{index + 1}/{total}] Processing: {display_name}")
    print(f"  URL: {url}")
    
    # Build filenames using new format
    screen_filename = build_filename(recording, 'esq')
    camera_filename = build_filename(recording, 'dir')
    screen_path = OUTPUT_DIR / screen_filename
    camera_path = OUTPUT_DIR / camera_filename
    
    if screen_path.exists() and camera_path.exists():
        if screen_path.stat().st_size > 100000 and camera_path.stat().st_size > 100000:
            print(f"  Both files already exist, skipping")
            result['status'] = 'skipped'
            result['streams_downloaded'] = ['screen', 'camera']
            return result
    
    # Collect signed video URLs from network traffic
    video_urls = {}  # stream_type -> url
    
    page = await context.new_page()
    
    # Listen for video requests to ssrweb.zoom.us
    def on_request(request):
        req_url = request.url
        if 'ssrweb.zoom.us' in req_url and '.mp4' in req_url and 'Policy=' in req_url:
            stream_type = get_stream_type(req_url)
            if stream_type != 'unknown' and stream_type not in video_urls:
                video_urls[stream_type] = req_url
                print(f"  ✓ Captured {stream_type} URL ({len(req_url)} chars)")
    
    page.on('request', on_request)
    
    print(f"  Loading page...")
    
    try:
        await page.goto(url, timeout=120000)
        await page.wait_for_load_state("domcontentloaded")
    except Exception as e:
        print(f"  Error loading page: {e}")
        result['error'] = str(e)
        await page.close()
        return result
    
    # Check for password
    password_input = await page.query_selector('input[type="password"]')
    if password_input:
        print("  Recording requires a password - skipping")
        result['error'] = 'Password required'
        await page.close()
        return result
    
    # Wait for video player
    print("  Waiting for video player...")
    try:
        await page.wait_for_selector('video', timeout=5000)
    except:
        pass
    
    await page.wait_for_timeout(1000)
    
    # Try to trigger video playback
    if len(video_urls) < 2:
        print("  Triggering playback...")
        await page.evaluate('''() => {
            document.querySelectorAll('video').forEach(v => {
                v.play().catch(() => {});
            });
        }''')
        await page.wait_for_timeout(1000)
    
    if not video_urls:
        print("  ✗ No video URLs captured")
        result['error'] = 'No video URLs found'
        await page.close()
        return result
    
    print(f"  Found {len(video_urls)} stream(s): {', '.join(video_urls.keys())}")
    
    # Get referer
    referer = 'https://sistemapoliedro.zoom.us/'
    
    # Get cookies from browser
    cookies = await context.cookies()
    print(f"  Cookies: {len(cookies)} cookies")
    
    # Download each stream with proper naming
    for stream_type, video_url in video_urls.items():
        # Map stream type to side name
        if stream_type == 'screen':
            side = 'esq'
        elif stream_type == 'camera':
            side = 'dir'
        else:
            side = stream_type
        
        output_filename = build_filename(recording, side)
        output_path = OUTPUT_DIR / output_filename
        
        if output_path.exists() and output_path.stat().st_size > 100000:
            print(f"  Skipping {stream_type} (already downloaded)")
            result['streams_downloaded'].append(stream_type)
            continue
        
        print(f"  Downloading {stream_type} stream -> {output_filename}")
        success = download_with_curl(video_url, output_path, cookies, referer)
        
        if success:
            result['streams_downloaded'].append(stream_type)
        else:
            result['streams_failed'].append(stream_type)
    
    await page.close()
    
    # Determine final status
    if len(result['streams_downloaded']) == 0:
        result['status'] = 'failed'
    elif len(result['streams_failed']) > 0:
        result['status'] = 'partial'
    else:
        result['status'] = 'success'
    
    return result


async def check_login_status(page) -> bool:
    """Check if user is logged in to Zoom."""
    await page.goto("https://sistemapoliedro.zoom.us/recording/", timeout=30000)
    await page.wait_for_load_state("networkidle", timeout=30000)
    
    current_url = page.url
    return 'signin' not in current_url and 'login' not in current_url


async def wait_for_manual_login(page):
    """Wait for user to manually log in to Zoom."""
    print("\n" + "=" * 60)
    print("LOGIN REQUIRED")
    print("=" * 60)
    print("Please log in to Zoom in the browser window.")
    print("Your login will be saved for future runs.")
    print("\nOnce logged in, press Enter here to continue...")
    print("=" * 60)
    
    await page.goto("https://zoom.us/signin")
    await page.wait_for_load_state("networkidle")
    
    await asyncio.get_event_loop().run_in_executor(None, input)
    
    if await check_login_status(page):
        print("Login successful!")
        return True
    else:
        print("Login verification failed. Please try again.")
        return False


def save_results_csv(filepath: Path, recordings: list[dict]):
    """Save recording results to CSV file in same format as input."""
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['Disciplina', 'Semestre', 'Data', 'Professor', 'Frente', 'Conteúdo / Link da aula', 'Link', 'Expected Name', 'Error'])
        for rec in recordings:
            info = rec.get('recording', rec)
            # Build expected filename base
            expected_name = f"{info.get('semestre', '')} - {info.get('disciplina', '')} - {info.get('frente', '')} - {info.get('date', '')} - {info.get('title', rec.get('title', ''))}"
            expected_name = sanitize_filename(expected_name)
            writer.writerow([
                info.get('disciplina', ''),
                info.get('semestre', ''),
                info.get('date', ''),
                info.get('professor', ''),
                info.get('frente', ''),
                info.get('title', rec.get('title', '')),
                info.get('url', rec.get('url', '')),
                expected_name,
                rec.get('error', '')
            ])


async def main():
    if not CSV_FILE.exists():
        print(f"Error: CSV file not found: {CSV_FILE}")
        print("Expected format: title,zoom_url")
        return
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    FIREFOX_PROFILE_DIR.mkdir(exist_ok=True)
    
    recordings = load_recordings_from_csv(CSV_FILE)
    print(f"Loaded {len(recordings)} recordings from CSV")
    
    if not recordings:
        print("No recordings to process")
        return
    
    # Track results
    successful = []
    partial = []
    failed = []
    skipped = []
    
    async with async_playwright() as p:
        print(f"\nUsing Firefox profile at: {FIREFOX_PROFILE_DIR.absolute()}")
        
        # Use Firefox to match the working curl User-Agent
        context = await p.firefox.launch_persistent_context(
            user_data_dir=str(FIREFOX_PROFILE_DIR.absolute()),
            headless=True,
            accept_downloads=True,
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        print("\nChecking login status...")
        if await check_login_status(page):
            print("Already logged in!")
        else:
            while not await wait_for_manual_login(page):
                pass
        
        await page.close()
        
        # Process recordings
        for i, recording in enumerate(recordings):
            try:
                result = await process_recording(context, recording, i, len(recordings))
                
                if result['status'] == 'success':
                    successful.append(result)
                elif result['status'] == 'partial':
                    partial.append(result)
                elif result['status'] == 'skipped':
                    skipped.append(result)
                else:
                    failed.append(result)
                    
            except Exception as e:
                print(f"  Error: {e}")
                failed.append({
                    'title': recording['title'],
                    'url': recording['url'],
                    'error': str(e)
                })
        
        await context.close()
    
    # Print summary
    print("\n" + "=" * 60)
    print("DOWNLOAD COMPLETE")
    print("=" * 60)
    print(f"  ✓ Successful (both streams): {len(successful)}")
    print(f"  ⚠ Partial (one stream only): {len(partial)}")
    print(f"  ✗ Failed: {len(failed)}")
    print(f"  ○ Skipped (already existed): {len(skipped)}")
    
    # Save failed downloads to CSV for retry
    if failed:
        failed_csv = OUTPUT_DIR / "failed_downloads.csv"
        save_results_csv(failed_csv, failed)
        print(f"\n  Failed recordings saved to: {failed_csv}")
        print("  Failed recordings:")
        for rec in failed:
            error = rec.get('error', 'Unknown error')
            print(f"    - {rec['title']}: {error}")
    
    # Save partial downloads to CSV for manual check
    if partial:
        partial_csv = OUTPUT_DIR / "partial_downloads.csv"
        save_results_csv(partial_csv, partial)
        print(f"\n  Partial recordings saved to: {partial_csv}")
        print("  Partial recordings (need manual check):")
        for rec in partial:
            downloaded = ', '.join(rec.get('streams_downloaded', []))
            failed_streams = ', '.join(rec.get('streams_failed', []))
            print(f"    - {rec['title']}: got [{downloaded}], missing [{failed_streams}]")
    
    print(f"\nDownloads saved to: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    asyncio.run(main())
