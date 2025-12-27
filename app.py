from flask import Flask, render_template, request, redirect, url_for
import os
import zipfile
import subprocess
import signal
import shutil

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
MAX_RUNNING = 5

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# app_name -> subprocess
processes = {}


# ---------- Helper Functions ----------

def extract_zip(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(extract_to)


def install_requirements(path):
    req = os.path.join(path, "requirements.txt")
    if os.path.exists(req):
        subprocess.call(["pip", "install", "-r", req])


def find_main_file(path):
    for f in ["main.py", "app.py", "bot.py"]:
        if os.path.exists(os.path.join(path, f)):
            return f
    return None


def start_app(app_name):
    app_dir = os.path.join(UPLOAD_FOLDER, app_name)
    zip_path = os.path.join(app_dir, "app.zip")
    extract_dir = os.path.join(app_dir, "extracted")
    log_path = os.path.join(app_dir, "logs.txt")

    if not os.path.exists(extract_dir):
        extract_zip(zip_path, extract_dir)
        install_requirements(extract_dir)

    main_file = find_main_file(extract_dir)
    if not main_file:
        return

    log = open(log_path, "a")

    p = subprocess.Popen(
        ["python3", main_file],
        cwd=extract_dir,
        stdout=log,
        stderr=log
    )

    processes[app_name] = p


def stop_app(app_name):
    p = processes.get(app_name)
    if p:
        p.send_signal(signal.SIGTERM)
        processes.pop(app_name, None)


# ---------- Routes ----------

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("file")
        if file and file.filename.endswith(".zip"):
            app_name = file.filename.replace(".zip", "")
            app_dir = os.path.join(UPLOAD_FOLDER, app_name)
            os.makedirs(app_dir, exist_ok=True)
            file.save(os.path.join(app_dir, "app.zip"))

    apps = []
    for name in os.listdir(UPLOAD_FOLDER):
        app_dir = os.path.join(UPLOAD_FOLDER, name)
        log_file = os.path.join(app_dir, "logs.txt")
        log_data = ""

        if os.path.exists(log_file):
            with open(log_file, "r", errors="ignore") as f:
                log_data = f.read()[-3000:]

        apps.append({
            "name": name,
            "running": name in processes,
            "log": log_data
        })

    return render_template("index.html", apps=apps)


@app.route("/run/<name>")
def run(name):
    if name not in processes and len(processes) < MAX_RUNNING:
        start_app(name)
    return redirect(url_for("index"))


@app.route("/stop/<name>")
def stop(name):
    stop_app(name)
    return redirect(url_for("index"))


@app.route("/restart/<name>")
def restart(name):
    stop_app(name)
    start_app(name)
    return redirect(url_for("index"))


@app.route("/delete/<name>")
def delete(name):
    # stop if running
    stop_app(name)

    app_dir = os.path.join(UPLOAD_FOLDER, name)
    if os.path.exists(app_dir):
        shutil.rmtree(app_dir)

    return redirect(url_for("index"))


# ---------- Main ----------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)