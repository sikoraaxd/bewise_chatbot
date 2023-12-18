from flask import Flask, request, jsonify, make_response
import jwt
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'b146ea7a8ce64f789cc376653b454c6d'

def token_required(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        token = request.args.get('Authorization')
        if not token:
            return jsonify({'Error': 'Token is required!'}), 401
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            print(payload)
        except jwt.ExpiredSignatureError:
            return jsonify({'Error': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'Error': 'Invalid token!'}), 401
        return func(*args, **kwargs)
    return decorated


@app.route('/')
def home():
    return 'Hello World!'


@app.route('/login', methods=['GET'])
@token_required
def login():
    return 'Token is verified!'


@app.route('/auth', methods=['POST'])
def auth():
    try:
        user_id = request.args.get('user_id')
        account_id = request.args.get('account_id')
        token = jwt.encode({
            'user_id': user_id,
            'account_id': account_id,
            'exp': datetime.utcnow() + timedelta(minutes=30)
        },
        app.config['SECRET_KEY'])
        print(token)
        return jsonify({'Token': token})
    except:
        return jsonify({'Error': 'Invalid data!'}), 400

if __name__ == '__main__':
    app.run(debug=True)