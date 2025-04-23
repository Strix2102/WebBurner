import os
import subprocess
import tempfile
import wave
from flask import Flask, request, render_template_string, redirect, url_for, flash, send_file

UPLOAD_FOLDER = "/tmp/audio_uploads"
WAV_FOLDER = "/tmp/audio_wavs"
LOG_FOLDER = "/tmp/burn_logs"
CD_DEVICE = "/dev/sr0"
MAX_DURATION_SECONDS = 80 * 60

app = Flask(__name__)
app.secret_key = "supersecretkey"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(WAV_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Audio CD Burner</title>
    <style>
        body { text-align: center; font-family: Arial, sans-serif; }
        h1, h2 { margin-top: 20px; }
        ul { list-style: none; padding: 0; }
        li { margin: 5px 0; }
        form { margin: 15px auto; display: inline-block; }
        input[type="submit"] { margin: 5px 10px; padding: 8px 20px; }
        .progress-bar { width: 50%; margin: 20px auto; border: 1px solid #ccc; height: 20px; position: relative; }
        .progress-fill { height: 100%; background-color: #4caf50; width: 0%; transition: width 0.5s ease-in-out; }
    </style>
    <script>
        function showProgress() {
            const progress = document.getElementById('progress');
            if (progress) {
                let width = 0;
                const interval = setInterval(() => {
                    if (width >= 100) {
                        clearInterval(interval);
                    } else {
                        width += 1;
                        document.getElementById('bar').style.width = width + '%';
                    }
                }, 100);
            }
        }
    </script>
</head>
<body>
<h1>Upload Audio Files (MP3 or WAV)</h1>
{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul>
    {% for message in messages %}
      <li><strong>{{ message }}</strong></li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
<form method="post" action="/upload" enctype="multipart/form-data">
  <input type="file" name="files" multiple>
  <input type="submit" value="Upload">
</form>
<h2>Uploaded Files:</h2>
<ul>
  {% for f in files %}
    <li>{{ f }}</li>
  {% endfor %}
</ul>
<div class="progress-bar" id="progress"><div class="progress-fill" id="bar"></div></div>
<form method="get" action="/confirm" onsubmit="showProgress()">
  <input type="submit" value="Proceed to Burn">
</form>
<form method="get" action="/simulate">
  <input type="submit" value="Simulate Burn (This is broken)">
</form>
<form method="post" action="/clear">
  <input type="submit" value="Clear Uploaded Files">
</form>
</body>
</html>
'''

def get_uploaded_files():
    return sorted(os.listdir(UPLOAD_FOLDER))

def calculate_wav_duration(filepath):
    try:
        with wave.open(filepath, 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate)
    except:
        return 0

def prepare_wavs():
    for f in os.listdir(WAV_FOLDER):
        os.remove(os.path.join(WAV_FOLDER, f))
    uploaded_files = get_uploaded_files()
    total_duration = 0
    wav_files = []
    for f in uploaded_files:
        full_path = os.path.join(UPLOAD_FOLDER, f)
        wav_path = os.path.join(WAV_FOLDER, os.path.splitext(f)[0] + ".wav")
        subprocess.run(["ffmpeg", "-y", "-i", full_path, "-ar", "44100", "-ac", "2", "-sample_fmt", "s16", wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wav_files.append(wav_path)
        total_duration += calculate_wav_duration(wav_path)
    return wav_files, total_duration, uploaded_files

def generate_toc(wav_files):
    toc_path = os.path.join(tempfile.gettempdir(), "audio.toc")
    with open(toc_path, "w") as toc:
        toc.write("CD_DA\n\n")
        toc.write("CD_TEXT {\n")
        toc.write("  LANGUAGE_MAP {\n")
        toc.write("    0 : EN\n")
        toc.write("  }\n")
        toc.write("  LANGUAGE 0 {\n")
        toc.write("    TITLE \"Album Title\"\n")
        toc.write("    PERFORMER \"Album Artist\"\n")
        toc.write("    DISC_ID \"XYZ123\"\n")
        toc.write("    UPC_EAN \"\"\n")
        toc.write("  }\n")
        toc.write("}\n\n")
        for f in wav_files:
            track_title = os.path.splitext(os.path.basename(f))[0]
            toc.write("TRACK AUDIO\n")
            toc.write("  CD_TEXT {\n")
            toc.write("    LANGUAGE 0 {\n")
            toc.write(f"      TITLE \"{track_title}\"\n")
            toc.write(f"      PERFORMER \"Track Artist\"\n")
            toc.write("    }\n")
            toc.write("  }\n")
            toc.write(f"  FILE \"{f}\" 0:00:00\n\n")
    return toc_path

def burn_cd(wav_files):
    toc_path = generate_toc(wav_files)
    log_path = os.path.join(LOG_FOLDER, "burn_log.txt")
    try:
        result = subprocess.run(
            ["cdrdao", "write", "--driver", "generic-mmc", "--device", CD_DEVICE, "--eject", "--full-burn", "-v", "4", toc_path],
            capture_output=True, text=True, timeout=600
        )
        with open(log_path, "w") as log:
            log.write(result.stdout + "\n" + result.stderr)
        app.config['last_log_path'] = log_path
        if result.returncode != 0:
            raise RuntimeError("Burn process failed. Check log.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Burn process timed out.")
    except Exception as e:
        raise RuntimeError(f"An error occurred: {str(e)}")

@app.route("/confirm")
def confirm():
    try:
        wav_files, total_duration, _ = prepare_wavs()
        if total_duration > MAX_DURATION_SECONDS:
            raise RuntimeError("Total duration exceeds 80 minutes.")
        burn_cd(wav_files)
        return render_template_string("""
        <h2>Burn Complete</h2>
        <a href="/download_log">Download Burn Log</a><br>
        <a href="/">Back to Home</a>
        """)
    except Exception as e:
        return render_template_string(f"""
        <h2>Burn Error</h2>
        <p>{str(e)}</p>
        <a href="/download_log">Download Log</a><br>
        <a href="/">Back to Home</a>
        """)

@app.route("/simulate")
def simulate():
    try:
        wav_files, _, _ = prepare_wavs()
        toc_path = generate_toc(wav_files)
        log_path = os.path.join(LOG_FOLDER, "simulation_log.txt")
        result = subprocess.run(
            ["cdrdao", "simulate", "--driver", "generic-mmc-raw", "--device", CD_DEVICE, "-v", "3", toc_path],
            capture_output=True, text=True, timeout=600
        )
        with open(log_path, "w") as log:
            log.write(result.stdout + "\n" + result.stderr)
        app.config['last_log_path'] = log_path
        if result.returncode != 0:
            raise RuntimeError("Simulation failed. <a href='/download_log'>Download Simulation Log</a>")
        return render_template_string("""
        <h2>Simulation Complete</h2>
        <p>No errors reported. You can now try a real burn if desired.</p>
        <a href="/download_log">Download Simulation Log</a><br>
        <a href="/">Back to Home</a>
        """)
    except Exception as e:
        return render_template_string(f"""
        <h2>Simulation Error</h2>
        <p>{str(e)}</p>
        <a href="/download_log">Download Log</a><br>
        <a href="/">Back to Home</a>
        """)

@app.route("/upload", methods=["POST"])
def upload():
    if 'files' not in request.files:
        flash("No files part in request")
        return redirect(url_for('index'))
    files = request.files.getlist("files")
    for file in files:
        if file:
            file.save(os.path.join(UPLOAD_FOLDER, file.filename))
    flash("Files uploaded successfully.")
    return redirect(url_for('index'))

@app.route("/clear", methods=["POST"])
def clear():
    for f in os.listdir(UPLOAD_FOLDER):
        os.remove(os.path.join(UPLOAD_FOLDER, f))
    for f in os.listdir(WAV_FOLDER):
        os.remove(os.path.join(WAV_FOLDER, f))
    flash("Uploaded files cleared.")
    return redirect(url_for('index'))

@app.route("/")
def index():
    files = get_uploaded_files()
    return render_template_string(HTML_TEMPLATE, files=files)

@app.route("/download_log")
def download_log():
    path = app.config.get('last_log_path')
    if path and os.path.exists(path):
        return send_file(path, as_attachment=True)
    else:
        return "Log file not found."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
