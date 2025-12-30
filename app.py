import os
import json
import time
from flask import Flask, render_template, request, Response, jsonify
from werkzeug.utils import secure_filename
from torrent_wrapper import get_torrent_output_info
from torrent_wrapper import manager

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DOWNLOAD_FOLDER'] = 'downloads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_download():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        filename = secure_filename(file.filename)
        torrent_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(torrent_path)
        
        success = manager.start_download(
            torrent_path,
            app.config['DOWNLOAD_FOLDER']
        )

        if success:
            return jsonify({"message": "Download started"})
        else:
            return jsonify({"error": "Download already in progress"}), 409

@app.route('/stop', methods=['POST'])
def stop_download():
    manager.stop_download()
    return jsonify({"message": "Download stopping..."})

@app.route('/stream')
def stream():
    def event_stream():
        while True:
            data = manager.get_stream_data()
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(0.5)
            
    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == '__main__':
    app.run(debug=True, threaded=True, port=5000)