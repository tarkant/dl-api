import subprocess
import os
from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.responses import FileResponse
import uuid
from fastapi import BackgroundTasks
from starlette.status import HTTP_401_UNAUTHORIZED

app = FastAPI()

# API Key configuration
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY environment variable must be set!")

def verify_api_key(request: Request):
    api_key = request.headers.get("x-api-key")
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key.")

# Directory to store downloaded files temporarily
DOWNLOAD_DIR = "temp_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@app.post("/download/")
async def download_video(
    url: str = Query(..., description="URL of the video to download"),
    output_format: str = Query("mp4", description="Desired output format (e.g., mp4, mkv, mp3)"),
    request: Request = None,
    _: None = Depends(verify_api_key)
):
    """
    Downloads a video from the given URL in the specified format.
    """
    try:
        # Generate a unique filename to avoid collisions
        unique_id = str(uuid.uuid4())
        # Define the output filename and path.
        # yt-dlp can sometimes add its own extension, so we'll aim for a base name.
        base_output_filename = f"{unique_id}"
        output_path_template = os.path.join(DOWNLOAD_DIR, f"{base_output_filename}.%(ext)s")
        final_output_filename_placeholder = f"{base_output_filename}.{output_format}" # Placeholder for checking

        # Construct the yt-dlp command
        # Forcing format and output template.
        # Using -f best[ext=mp4]/best for video or bestaudio[ext=mp3]/bestaudio for audio as an example.
        # You might want to refine format selection based on 'output_format'
        if output_format in ["mp3", "m4a", "wav", "aac", "opus", "flac"]: # Audio formats
            format_selection = f"bestaudio[ext={output_format}]/bestaudio"
            # Forcing audio format conversion if yt-dlp doesn't download it directly.
            # Note: This requires ffmpeg to be installed in the Docker container.
            cmd = [
                "yt-dlp",
                "-x", # Extract audio
                "--audio-format", output_format,
                url,
                "-o", output_path_template,
            ]
        else: # Video formats
            format_selection = f"bestvideo[ext={output_format}]+bestaudio/best[ext={output_format}]/best"
            cmd = [
                "yt-dlp",
                "-f", format_selection,
                url,
                "-o", output_path_template,
                "--merge-output-format", output_format, # Ensure merged files get the right extension
            ]

        # Execute the command
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            # Log stderr for debugging
            error_message = stderr.decode('utf-8', errors='ignore').strip()
            print(f"yt-dlp error: {error_message}")
            raise HTTPException(status_code=500, detail=f"yt-dlp failed: {error_message}")

        # Find the actual downloaded file (yt-dlp might adjust the filename)
        downloaded_file = None
        # yt-dlp appends the actual extension it downloaded or converted to.
        # We need to find the file that starts with unique_id and has the requested output_format
        # or the extension yt-dlp chose if conversion happened.
        for f_name in os.listdir(DOWNLOAD_DIR):
            if f_name.startswith(unique_id):
                if f_name.endswith(f".{output_format}"): # Exact match
                    downloaded_file = os.path.join(DOWNLOAD_DIR, f_name)
                    break
                # Fallback if yt-dlp used a different extension after conversion (e.g. for audio)
                if output_format in ["mp3", "m4a", "wav"] and f_name.startswith(unique_id):
                     downloaded_file = os.path.join(DOWNLOAD_DIR, f_name)
                     break


        if not downloaded_file or not os.path.exists(downloaded_file):
            # Try to get the exact output filename from yt-dlp's stdout if possible
            # This part can be tricky as yt-dlp output varies.
            # A more robust way is to use --print filename and capture that.
            # For now, we'll rely on the unique_id prefix.
            print(f"Could not find downloaded file starting with {unique_id} and format {output_format} in {DOWNLOAD_DIR}")
            print(f"Files in dir: {os.listdir(DOWNLOAD_DIR)}")
            raise HTTPException(status_code=500, detail="File not found after download. yt-dlp might have used a different name or format.")

        # Return the file and then delete it
        return FileResponse(
            path=downloaded_file,
            filename=os.path.basename(downloaded_file), # Send it with its actual name
            media_type='application/octet-stream', # Generic binary type
            background_tasks=BackgroundTask(os.remove, downloaded_file) # Delete after sending
        )

    except HTTPException as e:
        raise e # Re-raise HTTPException
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

# To allow cleanup of files if the server is stopped, though this is more for graceful shutdowns
# and won't catch all termination signals, especially in Docker.
import atexit
import shutil

def cleanup_temp_files():
    print(f"Cleaning up temporary files in {DOWNLOAD_DIR}...")
    try:
        shutil.rmtree(DOWNLOAD_DIR)
        os.makedirs(DOWNLOAD_DIR, exist_ok=True) # Recreate for next run
    except Exception as e:
        print(f"Error during cleanup: {e}")

atexit.register(cleanup_temp_files)

@app.post("/download_and_cleanup/") # Renamed to avoid conflict if testing both
async def download_video_with_cleanup(
    url: str = Query(..., description="URL of the video to download"),
    output_format: str = Query("mp4", description="Desired output format (e.g., mp4, mkv, mp3)"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    request: Request = None,
    _: None = Depends(verify_api_key)
):
    """
    Downloads a video from the given URL in the specified format.
    The downloaded file is deleted from the server after being sent.
    """
    try:
        unique_id = str(uuid.uuid4())
        base_output_filename = f"{unique_id}"
        # Use a template that yt-dlp understands for setting the extension
        output_path_template = os.path.join(DOWNLOAD_DIR, f"{base_output_filename}.%(ext)s")
        # This will be the target file name we look for after download
        target_output_filename = f"{base_output_filename}.{output_format}"
        target_output_path = os.path.join(DOWNLOAD_DIR, target_output_filename)


        cmd_args = [
            "yt-dlp",
            url,
            # Output template tells yt-dlp where to save and what to name the file.
            # %(ext)s will be replaced by yt-dlp with the actual extension.
            "-o", output_path_template,
        ]

        # Format selection:
        # For specific video format: -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        # For specific audio format: -f "bestaudio[ext=mp3]/bestaudio" -x --audio-format mp3
        if output_format in ["mp3", "m4a", "wav", "aac", "flac", "opus"]: # Audio formats
            cmd_args.extend([
                "-f", f"bestaudio[ext={output_format}]/bestaudio", # Prefer direct download of format
                "-x", # Extract audio
                "--audio-format", output_format, # Convert if necessary (requires ffmpeg)
            ])
        else: # Video formats
            cmd_args.extend([
                # Prefer video in requested container, merge with best audio.
                # Fallback to best video in any format if specific not available.
                "-f", f"bestvideo[ext={output_format}]+bestaudio/best[ext={output_format}]/best",
                "--merge-output-format", output_format, # Ensure final container is what's requested
            ])

        print(f"Executing command: {' '.join(cmd_args)}")
        process = subprocess.Popen(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            error_message = stderr.decode('utf-8', errors='ignore').strip()
            print(f"yt-dlp error: {error_message}")
            raise HTTPException(status_code=500, detail=f"yt-dlp execution failed: {error_message}")

        # Determine the actual downloaded file path.
        # yt-dlp will name the file based on output_path_template, replacing %(ext)s.
        # We need to find this file. It should start with unique_id.
        downloaded_file_actual_path = None
        for f_name in os.listdir(DOWNLOAD_DIR):
            if f_name.startswith(unique_id) and f_name.endswith(f".{output_format}"):
                downloaded_file_actual_path = os.path.join(DOWNLOAD_DIR, f_name)
                break
            # Fallback for audio that might get a different extension if only conversion was possible
            # e.g., asking for mp3, but yt-dlp downloads m4a then converts to mp3.
            # The --audio-format flag usually handles the final extension correctly.
            # If not, this part might need more robust logic, e.g., using yt-dlp --get-filename
            if output_format in ["mp3", "m4a", "wav", "aac", "flac", "opus"] and f_name.startswith(unique_id):
                 downloaded_file_actual_path = os.path.join(DOWNLOAD_DIR, f_name) # Take the first match
                 break


        if not downloaded_file_actual_path or not os.path.exists(downloaded_file_actual_path):
            print(f"Stdout from yt-dlp: {stdout.decode('utf-8', errors='ignore')}")
            print(f"Stderr from yt-dlp: {stderr.decode('utf-8', errors='ignore')}")
            print(f"Files in {DOWNLOAD_DIR}: {os.listdir(DOWNLOAD_DIR)}")
            raise HTTPException(status_code=500, detail=f"Downloaded file not found. Expected: {target_output_filename} or similar.")

        # Add the cleanup task to run after the response is sent
        background_tasks.add_task(os.remove, downloaded_file_actual_path)

        return FileResponse(
            path=downloaded_file_actual_path,
            filename=os.path.basename(downloaded_file_actual_path),
            media_type='application/octet-stream'
        )

    except HTTPException as e:
        # If the file was partially downloaded or exists and an error occurs later, try to clean it up.
        # This is a simplistic cleanup for this specific error path.
        potential_file_to_clean = os.path.join(DOWNLOAD_DIR, f"{unique_id}.{output_format}") # A guess
        if os.path.exists(potential_file_to_clean):
             try:
                 os.remove(potential_file_to_clean)
             except OSError:
                 pass # Ignore if removal fails
        raise e
    except Exception as e:
        # Similar cleanup attempt for generic exceptions
        potential_file_to_clean = os.path.join(DOWNLOAD_DIR, f"{unique_id}.{output_format}") # A guess
        if os.path.exists(potential_file_to_clean):
            try:
                os.remove(potential_file_to_clean)
            except OSError:
                pass
        print(f"An unexpected error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")