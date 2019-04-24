import os

import jsonpickle
from flask import Flask, request, redirect, send_file, Response, send_from_directory
import cv2
import numpy as np

UPLOAD_FOLDER = 'D:/BlockchainFileStore/'
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/imagestore/<hashstr>', methods=['POST'])
def upload(hashstr):
    r = request
    # convert string of image data to uint8
    nparr = np.fromstring(r.data, np.uint8)
    # decode image
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # do some fancy processing here....
    cv2.imwrite('D:/BlockchainFileStore/'+hashstr+'.jpg', img)
    # build a response dict to send back to client
    response = {'message': 'image received. size={}x{}'.format(img.shape[1], img.shape[0])
                }
    # encode response using jsonpickle
    response_pickled = jsonpickle.encode(response)

    return Response(response=response_pickled, status=200, mimetype="application/json")


@app.route("/imagestore/getimage/<hashstr>", methods=['GET'])
def get_file(hashstr):
    filename = hashstr+'.jpg'
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), attachment_filename=hashstr+'.JPG')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port='5005')
