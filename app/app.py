from flask import Flask, request, render_template, send_file
import subprocess
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "./originalzip"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        size = request.form.get("size")  # Canvas size
        resize_dim = request.form.get("resize")  # Max dimension
        file = request.files["zipfile"]

        if file and file.filename.endswith(".zip"):
            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"], secure_filename(file.filename)
            )
            file.save(filepath)

            # Run the bash script
            result = subprocess.check_output(
                ["bash", "process.sh", size, resize_dim], universal_newlines=True
            ).strip()

            # The last line is the path to the zip file
            zip_path = result.splitlines()[-1].strip()
            return send_file(zip_path, as_attachment=True)

    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
