import hashlib
import json
import os
import time
from urllib.parse import urlparse
from uuid import uuid4
import cv2
import requests
from flask import Flask, jsonify, request, render_template, redirect, url_for, send_file


class Blockchain:
    def __init__(self):
        self.current_transactions = []
        self.chain = []
        self.nodes = set()

        # Create the genesis block
        self.new_block(previous_hash='1', proof=100)

    def register_node(self, address):
        """
        Add a new node to the list of nodes
        :param address: Address of node. Eg. 'http://192.168.0.5:5000'
        """

        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            # Accepts an URL without scheme like '192.168.0.5:5000'.
            self.nodes.add(parsed_url.path)
        else:
            raise ValueError('Invalid URL')

    def valid_chain(self, chain):
        """
        Determine if a given blockchain is valid
        :param chain: A blockchain
        :return: True if valid, False if not
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")
            # Check that the hash of the block is correct
            last_block_hash = self.hash(last_block)
            if block['previous_hash'] != last_block_hash:
                return False
            # Check that the Proof of Work is correct
            if not self.valid_proof(last_block['proof'], block['proof'], last_block_hash):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        This is our consensus algorithm, it resolves conflicts
        by replacing our chain with the longest one in the network.
        :return: True if our chain was replaced, False if not
        """

        neighbours = self.nodes
        new_chain = None

        # We're only looking for chains longer than ours
        max_length = len(self.chain)

        # Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            self.chain = new_chain
            return True

        return False

    def new_block(self, proof, previous_hash):
        """
        Create a new Block in the Blockchain
        :param proof: The proof given by the Proof of Work algorithm
        :param previous_hash: Hash of previous Block
        :return: New Block
        """

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        # Reset the current list of transactions
        self.current_transactions = []

        self.chain.append(block)
        return block

    def new_transaction(self, owner, name, rollnumber, cgpa):
        """
        Creates a new transaction to go into the next mined Block
        :param sender: Address of the Sender
        :param recipient: Address of the Recipient
        :param amount: Amount
        :return: The index of the Block that will hold this transaction
        """
        self.current_transactions.append({
            'owner': owner,
            'name': name,
            'rollnumber': rollnumber,
            'cgpa': cgpa,
        })

        return self.last_block['index'] + 1

    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def hash(block):
        """
        Creates a SHA-256 hash of a Block
        :param block: Block
        """

        # We must make sure that the Dictionary is Ordered, or we'll have inconsistent hashes
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, last_block):
        """
        Simple Proof of Work Algorithm:
         - Find a number p' such that hash(pp') contains leading 4 zeroes
         - Where p is the previous proof, and p' is the new proof

        :param last_block: <dict> last Block
        :return: <int>
        """

        last_proof = last_block['proof']
        last_hash = self.hash(last_block)

        proof = 0
        while self.valid_proof(last_proof, proof, last_hash) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof, last_hash):
        """
        Validates the Proof
        :param last_proof: <int> Previous Proof
        :param proof: <int> Current Proof
        :param last_hash: <str> The hash of the Previous Block
        :return: <bool> True if correct, False if not.
        """

        guess = f'{last_proof}{proof}{last_hash}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"


# Instantiate the Node
app = Flask(__name__)

# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')

# Instantiate the Blockchain
blockchain = Blockchain()

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'certificates')
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/mine', methods=['POST'])
def mine():
    if request.method == 'POST':
        values = request.get_json()

        # Check that the required fields are in the POST'ed data
        required = ['name', 'rollnumber', 'cgpa']
        if not all(k in values for k in required):
            return 'Missing values', 400

        # We run the proof of work algorithm to get the next proof...
        last_block = blockchain.last_block
        proof = blockchain.proof_of_work(last_block)

        # We must receive a reward for finding the proof.
        # The sender is "0" to signify that this node has mined a new coin.
        blockchain.new_transaction(
            owner=node_identifier,
            name=values['name'],
            rollnumber=values['rollnumber'],
            cgpa=values['cgpa'],
        )

        # Forge the new Block by adding it to the chain
        previous_hash = blockchain.hash(last_block)
        block = blockchain.new_block(proof, previous_hash)

        response = {
            'message': "New Block Forged",
            'index': block['index'],
            'transactions': block['transactions'],
            'proof': block['proof'],
            'previous_hash': block['previous_hash'],
        }
        return jsonify(response), 200


""""
@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    # Check that the required fields are in the POST'ed data
    required = ['name', 'rollnumber', 'cgpa']
    if not all(k in values for k in required):
        return 'Missing values', 400
    # Create a new Transaction
    index = blockchain.new_transaction(values['name'], values['rollnumber'], values['cgpa'])

    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201
"""


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200


# Front-end begins here
@app.route('/home/', methods=['GET'])
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/mycertificates/', methods=['GET'])
def Mycertificates():
    url = "http://localhost:5000/chain"
    req = requests.get(url=url)
    senddict = []
    for x in dict(req.json())['chain']:
        try:
            transaction = x['transactions'][0]
            if transaction['owner'] == node_identifier:
                dic = {'previous_hash': x['previous_hash'], 'time': x['timestamp'], 'name': transaction['name'], 'rollnumber': transaction['rollnumber'],
                       'cgpa': transaction['cgpa']}
                senddict.append(dic)
        except IndexError:
            pass
    return render_template('mycertificates.html', path=UPLOAD_FOLDER, files=senddict)


@app.route('/dashboard/', methods=['GET'])
def Dashboard():
    return render_template('dashboard.html', message='', registermessage='')


@app.route('/dashboard/createnewchain', methods=['POST'])
def createnewchain():
    if request.method == 'POST':
        name = request.form['nameform']
        roll = request.form['rollnumberform']
        cgpa = request.form['cgpaform']
        data = {
            "name": name,
            "rollnumber": roll,
            "cgpa": cgpa
        }
        url = "http://localhost:5000/mine"
        req = requests.post(url=url, json=data)
        previous_hash = req.json()['previous_hash']
        return redirect('/dashboard/uploadimage/'+previous_hash)


@app.route('/dashboard/uploadimage/<hashstr>', methods=['GET'])
def UploadImageHTML(hashstr):
    return render_template('uploadimage.html', hashstr=hashstr)


@app.route('/dashboard/resolve', methods=['GET'])
def dashboardresolve():
    url = "http://localhost:5000/nodes/resolve"
    req = requests.get(url=url)
    if req.json()['message'] == 'Our chain is authoritative':
        return render_template('dashboard.html', message=req.json()['message'], registermessage='')
    return render_template('dashboard.html', message='Chain modified', registermessage='')


@app.route('/dashboard/register', methods=['POST'])
def dashboardregister():
    url = 'http://localhost:5000/nodes/register'
    if request.method == "POST":
        data = {
            "nodes": [request.form['address']]
        }
        req = requests.post(url=url, json=data)
        message = req.json()['message']
        return render_template("dashboard.html", registermessage=message)


@app.route("/imagestore/<hashstr>", methods=['GET', 'POST'])
def upload_file(hashstr):
    if request.method == 'POST':
        file_name = False
        # check if the post request has the file part
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            return redirect(request.url)
        if file:
            filename, file_extension = os.path.splitext(file.filename)
            file_name = hashstr + file_extension
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], hashstr + file_extension))
        addr = 'http://localhost:5005'
        test_url = addr + '/imagestore/' + hashstr
        # prepare headers for http request
        content_type = 'image/jpeg'
        headers = {'content-type': content_type}
        img = cv2.imread(os.path.join(UPLOAD_FOLDER, file_name))
        # encode image as jpeg
        _, img_encoded = cv2.imencode('.jpg', img)
        # send http request with image and receive response
        response = requests.post(test_url, data=img_encoded.tostring(), headers=headers)
    return redirect('/mycertificates/')


@app.route("/mycertificates/getimage/<imagename>", methods=['GET'])
def get_file(imagename):
    return send_file(os.path.join(UPLOAD_FOLDER, imagename), attachment_filename=imagename)


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port
    app.run(host='0.0.0.0', port=port)
