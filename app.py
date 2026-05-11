from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import json
import os
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# ডাটাবেস কনফিগারেশন (PostgreSQL support for Railway)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///hoisting.db')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ======================== ডাটাবেস মডেল ========================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    plan = db.Column(db.String(20), default='24h')
    plan_activated_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    server_config = db.Column(db.Text, default='{}')
    files_data = db.Column(db.Text, default='[]')
    
    server_is_running = db.Column(db.Boolean, default=False)
    server_start_time = db.Column(db.DateTime, nullable=True)
    
    logs = db.relationship('ServerLog', backref='user', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ServerLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# ======================== HTML টেমপ্লেট ========================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hoisting Bot Server | IFTEKHAR</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', sans-serif; }
        body {
            min-height: 100vh;
            background: linear-gradient(135deg, #0a0e2a 0%, #060b1f 100%);
            padding: 1rem;
        }
        .cyber-bg {
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background-image: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,255,255,0.03) 2px, rgba(0,255,255,0.03) 4px);
            pointer-events: none;
            z-index: 0;
        }
        .container { position: relative; z-index: 10; max-width: 1400px; margin: 0 auto; }
        
        .auth-card {
            background: rgba(8,18,38,0.95);
            backdrop-filter: blur(16px);
            border-radius: 2rem;
            border: 1px solid rgba(0,255,255,0.4);
            max-width: 480px;
            margin: 8vh auto;
            padding: 2rem;
        }
        .iftekhar-logo {
            font-size: 2rem;
            font-weight: 800;
            text-align: center;
            background: linear-gradient(135deg, #fff, #0ff, #f0f);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
        }
        .tab-switch { display: flex; gap: 1rem; margin: 1.5rem 0; border-bottom: 1px solid #2f4a7a; }
        .tab-btn {
            flex: 1; background: none; border: none; padding: 0.8rem;
            color: #8aa9d4; font-weight: 600; cursor: pointer;
        }
        .tab-btn.active { color: #0ff; border-bottom: 2px solid #0ff; }
        .auth-form { display: none; }
        .auth-form.active { display: block; }
        .input-field {
            width: 100%; background: #0a1a2ee0; border: 1px solid #2f6080;
            padding: 0.8rem; border-radius: 1rem; color: white; margin: 0.5rem 0 1rem;
        }
        .auth-btn {
            width: 100%; background: linear-gradient(95deg, #00c6ff, #2575fc);
            border: none; padding: 0.8rem; border-radius: 1.5rem;
            font-weight: bold; color: white; cursor: pointer;
        }
        
        .dashboard {
            display: none;
            background: rgba(6,14,28,0.92);
            backdrop-filter: blur(12px);
            border-radius: 1.5rem;
            border: 1px solid #2f6a8a;
            overflow: hidden;
        }
        .dashboard-header {
            display: flex; justify-content: space-between; align-items: center;
            flex-wrap: wrap; padding: 1.2rem 1.8rem;
            background: #030e1ce0; border-bottom: 1px solid #2f6080;
        }
        .plan-selector {
            padding: 1rem 1.8rem; background: #051020aa;
            border-bottom: 1px solid #2f4a6a;
            display: flex; gap: 1rem; flex-wrap: wrap;
        }
        .plan-badge {
            background: #0a1a2e; padding: 0.5rem 1.2rem;
            border-radius: 2rem; cursor: pointer;
            border: 1px solid #3a6a8a;
        }
        .plan-badge.active-plan { background: #0ff22a; border-color: #0ff; color: #000; font-weight: bold; }
        .main-layout { display: flex; flex-wrap: wrap; }
        .sidebar {
            width: 260px; background: #020c1ae0;
            border-right: 1px solid #2f6080; padding: 1rem 0;
        }
        .sidebar-item {
            padding: 0.8rem 1.5rem; cursor: pointer;
            color: #bbd4ff; border-left: 3px solid transparent;
        }
        .sidebar-item:hover, .sidebar-item.active {
            background: #0f2a4a; border-left-color: #0ff; color: #0ff;
        }
        .content-area { flex: 1; padding: 1.8rem; min-height: 550px; }
        .action-buttons { display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
        .action-btn {
            background: #1f4f6f; border: none; padding: 0.6rem 1.2rem;
            border-radius: 2rem; color: white; cursor: pointer;
            font-weight: bold; transition: 0.2s;
        }
        .action-btn:hover { transform: scale(1.02); opacity: 0.9; }
        .action-btn.danger { background: #aa3355; }
        .action-btn.success { background: #2a8f5f; }
        .action-btn.warning { background: #ff8844; color: #000; }
        .action-btn.primary { background: #00aa6f; }
        .info-card {
            background: #0a1430aa; border-radius: 1rem;
            padding: 1.2rem; margin-bottom: 1.2rem;
        }
        .status-badge { 
            display: inline-block; padding: 0.3rem 1rem; border-radius: 2rem; 
            font-size: 0.8rem; font-weight: bold;
        }
        .status-running { background: #2a8f5f; color: white; }
        .status-stopped { background: #aa3355; color: white; }
        .logout-btn { background: #ff5566aa; padding: 0.4rem 1rem; border-radius: 2rem; cursor: pointer; }
        .file-item { background: #0a1a2a; margin: 0.5rem 0; padding: 0.6rem; border-radius: 0.8rem; display: flex; justify-content: space-between; }
        .toast-msg { position: fixed; bottom: 20px; right: 20px; background: #2a8f5f; padding: 0.5rem 1rem; border-radius: 2rem; z-index: 100; }
        .server-status-card { background: #0a1a3a; border-radius: 1rem; padding: 0.8rem; margin-bottom: 1rem; text-align: center; }
    </style>
</head>
<body>
<div class="cyber-bg"></div>
<div class="container">
    <div id="authCard" class="auth-card">
        <div class="iftekhar-logo">⚡ IFTEKHAR ⚡</div>
        <div style="text-align: center; color: #8ac4ff;">HOISTING BOT SERVER</div>
        <div class="tab-switch">
            <button class="tab-btn active" data-tab="login">🔐 লগইন</button>
            <button class="tab-btn" data-tab="register">📝 রেজিস্টার</button>
        </div>
        <div id="loginForm" class="auth-form active">
            <form id="loginAuthForm"><input type="email" id="loginEmail" class="input-field" placeholder="Gmail" required><input type="password" id="loginPassword" class="input-field" placeholder="পাসওয়ার্ড" required><button type="submit" class="auth-btn">🚀 প্রবেশ করুন</button></form>
        </div>
        <div id="registerForm" class="auth-form">
            <form id="registerAuthForm"><input type="text" id="regName" class="input-field" placeholder="নাম" required><input type="email" id="regEmail" class="input-field" placeholder="Gmail" required><input type="password" id="regPassword" class="input-field" placeholder="পাসওয়ার্ড" required><button type="submit" class="auth-btn">✅ একাউন্ট তৈরি</button></form>
        </div>
    </div>

    <div id="dashboard" class="dashboard">
        <div class="dashboard-header">
            <div><h2 style="color:#aaf0ff;">🐍 HOISTING BOT SERVER</h2><small>IFTEKHAR কোর | ফ্রি হোস্টিং</small></div>
            <div><span id="userEmailDisplay"></span><button id="logoutMainBtn" class="logout-btn" style="margin-left:0.8rem;">⛁ লগআউট</button></div>
        </div>

        <div class="plan-selector" id="planSelector">
            <div class="plan-badge" data-plan="24h">⏱️ ২৪ ঘন্টা (ফ্রি)</div>
            <div class="plan-badge" data-plan="7d">📅 ৭ দিন (ফ্রি)</div>
            <div class="plan-badge" data-plan="1m">🌟 ১ মাস (ফ্রি)</div>
        </div>

        <div class="main-layout">
            <div class="sidebar">
                <div class="sidebar-item active" data-tab="overview">📊 Overview</div>
                <div class="sidebar-item" data-tab="manage">⚙️ Manage</div>
                <div class="sidebar-item" data-tab="files">📁 Files</div>
                <div class="sidebar-item" data-tab="addons">🧩 Addons</div>
                <div class="sidebar-item" data-tab="settings">⚙️ Settings</div>
            </div>
            <div class="content-area" id="dynamicContent">Loading...</div>
        </div>
    </div>
</div>
<div id="toastMsg" style="display:none;" class="toast-msg"></div>

<script>
    let currentTab = 'overview';
    let statusInterval = null;
    
    function showToast(msg, isError=false) {
        const toast = document.getElementById('toastMsg');
        toast.style.backgroundColor = isError ? '#aa3355' : '#2a8f5f';
        toast.innerText = msg;
        toast.style.display = 'block';
        setTimeout(() => toast.style.display = 'none', 3000);
    }
    
    async function apiCall(url, method, data) {
        const res = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: data ? JSON.stringify(data) : undefined
        });
        return await res.json();
    }
    
    async function getServerStatus() {
        const res = await apiCall('/api/server_status', 'GET');
        return res;
    }
    
    async function loadContent(tab) {
        const res = await fetch(`/api/content/${tab}`);
        const data = await res.json();
        document.getElementById('dynamicContent').innerHTML = data.html;
        attachEvents();
    }
    
    function attachEvents() {
        const startBtn = document.getElementById('startServerBtn');
        if(startBtn) startBtn.onclick = async () => {
            const res = await apiCall('/api/start_server', 'POST');
            showToast(res.message);
            updateStatusDisplay();
            loadContent(currentTab);
        };
        
        const stopBtn = document.getElementById('stopServerBtn');
        if(stopBtn) stopBtn.onclick = async () => {
            const res = await apiCall('/api/stop_server', 'POST');
            showToast(res.message);
            updateStatusDisplay();
            loadContent(currentTab);
        };
        
        const restartBtn = document.getElementById('restartServerBtn');
        if(restartBtn) restartBtn.onclick = async () => {
            showToast('সার্ভার রিস্টার্ট হচ্ছে...');
            await apiCall('/api/restart_server', 'POST');
            updateStatusDisplay();
            loadContent(currentTab);
        };
        
        const deployBtn = document.getElementById('newDeployBtn');
        if(deployBtn) deployBtn.onclick = async () => {
            const res = await apiCall('/api/deploy', 'POST');
            showToast(res.message);
        };
        
        const saveSettingsBtn = document.getElementById('saveSettingsBtn');
        if(saveSettingsBtn) saveSettingsBtn.onclick = async () => {
            const data = {
                name: document.getElementById('serverNameInput')?.value,
                description: document.getElementById('serverDescInput')?.value,
                main_file: document.getElementById('mainFileInput')?.value
            };
            const res = await apiCall('/api/settings', 'POST', data);
            showToast(res.message);
        };
        
        const deleteServerBtn = document.getElementById('deleteServerBtn');
        if(deleteServerBtn) deleteServerBtn.onclick = async () => {
            if(confirm('সার্ভার ডিলিট করবেন? সব ডাটা রিসেট হবে!')) {
                const res = await apiCall('/api/delete_server', 'POST');
                showToast(res.message);
                loadContent('settings');
            }
        };
        
        const uploadBtn = document.getElementById('uploadFileBtn');
        if(uploadBtn) {
            uploadBtn.onclick = () => document.getElementById('fileInput').click();
            document.getElementById('fileInput').onchange = async (e) => {
                const file = e.target.files[0];
                if(file) {
                    const formData = new FormData();
                    formData.append('file', file);
                    const res = await fetch('/api/upload', { method: 'POST', body: formData });
                    const data = await res.json();
                    showToast(data.message);
                    loadContent('files');
                }
            };
        }
        
        document.querySelectorAll('.delete-file-btn').forEach(btn => {
            btn.onclick = async () => {
                const filename = btn.getAttribute('data-filename');
                const res = await apiCall('/api/delete_file', 'POST', { filename });
                showToast(res.message);
                loadContent('files');
            };
        });
    }
    
    async function updateStatusDisplay() {
        const status = await getServerStatus();
        const statusSpan = document.getElementById('serverStatusSpan');
        const uptimeSpan = document.getElementById('uptimeSpan');
        if(statusSpan) {
            if(status.is_running) {
                statusSpan.innerHTML = '🟢 চলমান';
                statusSpan.className = 'status-badge status-running';
            } else {
                statusSpan.innerHTML = '🔴 বন্ধ';
                statusSpan.className = 'status-badge status-stopped';
            }
        }
        if(uptimeSpan && status.start_time) {
            uptimeSpan.innerHTML = status.start_time;
        }
    }
    
    async function changePlan(plan) {
        const res = await apiCall('/api/change_plan', 'POST', { plan });
        showToast(res.message);
        document.querySelectorAll('.plan-badge').forEach(b => b.classList.remove('active-plan'));
        document.querySelector(`.plan-badge[data-plan="${plan}"]`).classList.add('active-plan');
    }
    
    async function checkAuth() {
        const res = await fetch('/api/check_auth');
        const data = await res.json();
        if(data.logged_in) {
            document.getElementById('authCard').style.display = 'none';
            document.getElementById('dashboard').style.display = 'block';
            document.getElementById('userEmailDisplay').innerHTML = `👤 ${data.name} (${data.email})`;
            document.querySelectorAll('.plan-badge').forEach(b => {
                if(b.dataset.plan === data.plan) b.classList.add('active-plan');
                b.onclick = () => changePlan(b.dataset.plan);
            });
            loadContent(currentTab);
            if(statusInterval) clearInterval(statusInterval);
            statusInterval = setInterval(updateStatusDisplay, 3000);
        } else {
            document.getElementById('authCard').style.display = 'block';
            document.getElementById('dashboard').style.display = 'none';
            if(statusInterval) clearInterval(statusInterval);
        }
    }
    
    document.querySelectorAll('.sidebar-item').forEach(item => {
        item.onclick = () => {
            document.querySelectorAll('.sidebar-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            currentTab = item.dataset.tab;
            loadContent(currentTab);
        };
    });
    
    document.getElementById('loginAuthForm').onsubmit = async (e) => {
        e.preventDefault();
        const res = await apiCall('/api/login', 'POST', {
            email: document.getElementById('loginEmail').value,
            password: document.getElementById('loginPassword').value
        });
        if(res.success) { showToast('লগইন সফল!'); checkAuth(); }
        else showToast(res.message, true);
    };
    document.getElementById('registerAuthForm').onsubmit = async (e) => {
        e.preventDefault();
        const res = await apiCall('/api/register', 'POST', {
            name: document.getElementById('regName').value,
            email: document.getElementById('regEmail').value,
            password: document.getElementById('regPassword').value
        });
        showToast(res.message);
        if(res.success) document.querySelector('.tab-btn[data-tab="login"]').click();
    };
    document.getElementById('logoutMainBtn').onclick = async () => {
        await apiCall('/api/logout', 'POST');
        checkAuth();
    };
    
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('loginForm').classList.toggle('active', btn.dataset.tab === 'login');
            document.getElementById('registerForm').classList.toggle('active', btn.dataset.tab === 'register');
        };
    });
    
    checkAuth();
</script>
</body>
</html>
'''

# ======================== Flask রাউট ========================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/check_auth')
def check_auth():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            return {'logged_in': True, 'name': user.name, 'email': user.email, 'plan': user.plan}
    return {'logged_in': False}

@app.route('/api/server_status')
def get_server_status():
    if 'user_id' not in session:
        return {'is_running': False, 'start_time': None}
    user = User.query.get(session['user_id'])
    return {
        'is_running': user.server_is_running,
        'start_time': user.server_start_time.strftime('%Y-%m-%d %H:%M:%S') if user.server_start_time else None
    }

@app.route('/api/start_server', methods=['POST'])
def start_server():
    if 'user_id' not in session:
        return {'message': 'লগইন করুন'}
    
    user = User.query.get(session['user_id'])
    if user.server_is_running:
        return {'message': 'সার্ভার ইতিমধ্যে চলমান!'}
    
    user.server_is_running = True
    user.server_start_time = datetime.utcnow()
    
    log = ServerLog(user_id=user.id, action='start')
    db.session.add(log)
    db.session.commit()
    
    return {'message': '✅ সার্ভার স্টার্ট করা হয়েছে!'}

@app.route('/api/stop_server', methods=['POST'])
def stop_server():
    if 'user_id' not in session:
        return {'message': 'লগইন করুন'}
    
    user = User.query.get(session['user_id'])
    if not user.server_is_running:
        return {'message': 'সার্ভার ইতিমধ্যে বন্ধ!'}
    
    user.server_is_running = False
    
    log = ServerLog(user_id=user.id, action='stop')
    db.session.add(log)
    db.session.commit()
    
    return {'message': '⏹️ সার্ভার বন্ধ করা হয়েছে!'}

@app.route('/api/restart_server', methods=['POST'])
def restart_server():
    if 'user_id' not in session:
        return {'message': 'লগইন করুন'}
    
    user = User.query.get(session['user_id'])
    user.server_is_running = False
    db.session.commit()
    
    user.server_is_running = True
    user.server_start_time = datetime.utcnow()
    
    log = ServerLog(user_id=user.id, action='restart')
    db.session.add(log)
    db.session.commit()
    
    return {'message': '🔄 সার্ভার রিস্টার্ট সম্পন্ন!'}

@app.route('/api/deploy', methods=['POST'])
def deploy():
    if 'user_id' not in session:
        return {'message': 'লগইন করুন'}
    
    log = ServerLog(user_id=session['user_id'], action='deploy')
    db.session.add(log)
    db.session.commit()
    return {'message': '🚀 নতুন ডিপ্লয় তৈরি হয়েছে! সব বট নোড আপডেটেড।'}

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    if User.query.filter_by(email=data['email']).first():
        return {'success': False, 'message': 'এই ইমেইল ইতিমধ্যে রেজিস্টার করা আছে!'}
    
    user = User(
        name=data['name'],
        email=data['email'],
        server_config=json.dumps({
            'server_id': secrets.token_hex(16),
            'name': 'My Hoisting Bot',
            'description': '',
            'main_file': 'main.py',
            'env_variables': [{'key': 'CLIENT_KEY', 'value': 'SECRET'}]
        })
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return {'success': True, 'message': 'রেজিস্ট্রেশন সফল! লগইন করুন।'}

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if user and user.check_password(data['password']):
        session['user_id'] = user.id
        return {'success': True, 'message': 'লগইন সফল'}
    return {'success': False, 'message': 'ভুল ইমেইল বা পাসওয়ার্ড'}

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return {'success': True}

@app.route('/api/change_plan', methods=['POST'])
def change_plan():
    if 'user_id' not in session:
        return {'message': 'লগইন করুন'}
    user = User.query.get(session['user_id'])
    plan = request.json['plan']
    user.plan = plan
    user.plan_activated_at = datetime.utcnow()
    db.session.commit()
    return {'message': f'{plan} প্ল্যান সক্রিয়!'}

@app.route('/api/content/<tab>')
def get_content(tab):
    if 'user_id' not in session:
        return {'html': '<p>লগইন করুন</p>'}
    user = User.query.get(session['user_id'])
    config = json.loads(user.server_config) if user.server_config else {}
    env_vars = config.get('env_variables', [])
    files = json.loads(user.files_data) if user.files_data else []
    
    status_html = f'''
    <div class="server-status-card">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
            <span>🤖 সার্ভার স্ট্যাটাস: </span>
            <span id="serverStatusSpan" class="status-badge {'status-running' if user.server_is_running else 'status-stopped'}">
                {'🟢 চলমান' if user.server_is_running else '🔴 বন্ধ'}
            </span>
        </div>
        {f'<div style="margin-top: 0.5rem;">⏱️ শুরু: {user.server_start_time.strftime("%Y-%m-%d %H:%M:%S") if user.server_start_time else "—"}</div>' if user.server_start_time else ''}
    </div>
    '''
    
    action_buttons = f'''
    <div class="action-buttons">
        {f'<button id="startServerBtn" class="action-btn success">▶️ START</button>' if not user.server_is_running else ''}
        {f'<button id="stopServerBtn" class="action-btn danger">⏹️ STOP</button>' if user.server_is_running else ''}
        <button id="restartServerBtn" class="action-btn warning">🔄 RESTART</button>
        <button id="newDeployBtn" class="action-btn primary">🚀 NEW DEPLOY</button>
    </div>
    '''
    
    if tab == 'overview':
        html = f'''
        {status_html}
        {action_buttons}
        <div class="info-card">
            <h3>📊 সার্ভার ওভারভিউ</h3>
            <p>📦 সক্রিয় প্ল্যান: <strong>{user.plan}</strong> (ফ্রি)</p>
            <p>📁 মোট ফাইল: {len(files)}</p>
            <p>🐍 পাইথন ভার্সন: 3.11.5</p>
            <p>🎮 বট নোড: {'সক্রিয়' if user.server_is_running else 'নিষ্ক্রিয়'}</p>
            <p>💾 মেমরি ব্যবহার: 256MB / 1GB</p>
        </div>
        '''
    elif tab == 'manage':
        html = f'''
        {status_html}
        {action_buttons}
        <div class="info-card">
            <h3>⚙️ ম্যানেজ বট নোড</h3>
            <p>✅ সক্রিয় বট প্রসেস: {'৩টি' if user.server_is_running else '০টি'}</p>
            <p>📡 হোইস্ট কানেকশন: {'সংযুক্ত' if user.server_is_running else 'বিচ্ছিন্ন'}</p>
        </div>
        '''
    elif tab == 'files':
        files_html = ''.join([f'<div class="file-item"><span>📄 {f["name"]} ({(f["size"]/1024):.1f} KB)</span><button class="delete-file-btn" data-filename="{f["name"]}">🗑️</button></div>' for f in files])
        html = f'''
        {status_html}
        <div><h3>📁 ফাইল ম্যানেজার</h3>
        <div style="border:2px dashed #2f6a8a; padding:1.5rem; text-align:center; border-radius:1rem;">
            <input type="file" id="fileInput" style="display:none;">
            <button id="uploadFileBtn" class="action-btn">📎 আপলোড ফাইল</button>
            <p style="margin-top:0.5rem; font-size:0.7rem;">সীমাহীন আপলোড (ফ্রি)</p>
        </div>
        <div class="file-list">{files_html if files_html else '<p>কোনো ফাইল নেই</p>'}</div></div>
        '''
    elif tab == 'addons':
        html = f'''
        {status_html}
        <h3>🧩 অ্যাডঅন</h3>
        <div class="info-card">🔌 Discord Hoist Bridge <button class="action-btn">ইনস্টল</button></div>
        <div class="info-card">🤖 Telegram Bot Connector <button class="action-btn">ইনস্টল</button></div>
        <div class="info-card">📊 Hoist Analytics <button class="action-btn">একটিভেট</button></div>
        '''
    else:
        env_rows = ''.join([f'<div class="env-row"><input type="text" class="env-key" value="{e["key"]}" placeholder="KEY"><input type="text" class="env-value" value="{e["value"]}" placeholder="VALUE"><button class="remove-env" onclick="this.parentElement.remove()">🗑️</button></div>' for e in env_vars])
        html = f'''
        {status_html}
        <h3>⚙️ সেটিংস</h3>
        <div class="info-card">
            <label>সার্ভার আইডি</label>
            <input type="text" id="serverIdInput" class="input-field" value="{config.get('server_id', 'N/A')}" readonly style="background:#0a1a2e80;">
            <label>নাম</label>
            <input type="text" id="serverNameInput" class="input-field" value="{config.get('name', '')}">
            <label>বিবরণ</label>
            <textarea id="serverDescInput" rows="2" class="input-field">{config.get('description', '')}</textarea>
            <label>মেইন ফাইল</label>
            <input type="text" id="mainFileInput" class="input-field" value="{config.get('main_file', 'main.py')}">
            <button id="saveSettingsBtn" class="action-btn success">💾 সেভ</button>
        </div>
        <div class="danger-zone">
            <h4 style="color:#ff6688;">⚠️ ডেঞ্জার জোন</h4>
            <button id="deleteServerBtn" class="delete-btn">🗑️ সার্ভার ডিলিট</button>
        </div>
        <div class="info-card">
            <h4>🔐 এনভায়রনমেন্ট ভেরিয়েবল</h4>
            <div id="envVarsContainer">{env_rows}</div>
            <button id="addEnvBtn" class="action-btn">+ অ্যাড</button>
            <div style="margin-top:1rem;"><button id="saveEnvBtn" class="action-btn success">💾 সেভ</button></div>
        </div>
        '''
    return {'html': html}

@app.route('/api/settings', methods=['POST'])
def save_settings():
    if 'user_id' not in session:
        return {'message': 'লগইন করুন'}
    user = User.query.get(session['user_id'])
    config = json.loads(user.server_config) if user.server_config else {}
    data = request.json
    config['name'] = data.get('name', '')
    config['description'] = data.get('description', '')
    config['main_file'] = data.get('main_file', 'main.py')
    user.server_config = json.dumps(config)
    db.session.commit()
    return {'message': 'সেটিংস সংরক্ষিত!'}

@app.route('/api/env', methods=['POST'])
def save_env():
    if 'user_id' not in session:
        return {'message': 'লগইন করুন'}
    user = User.query.get(session['user_id'])
    config = json.loads(user.server_config) if user.server_config else {}
    config['env_variables'] = request.json.get('env_vars', [])
    user.server_config = json.dumps(config)
    db.session.commit()
    return {'message': 'এনভায়রনমেন্ট ভেরিয়েবল সংরক্ষিত!'}

@app.route('/api/delete_server', methods=['POST'])
def delete_server():
    if 'user_id' not in session:
        return {'message': 'লগইন করুন'}
    user = User.query.get(session['user_id'])
    user.server_config = json.dumps({
        'server_id': secrets.token_hex(16),
        'name': 'Restored Server',
        'description': '',
        'main_file': 'main.py',
        'env_variables': []
    })
    user.files_data = '[]'
    user.server_is_running = False
    user.server_start_time = None
    db.session.commit()
    return {'message': 'সার্ভার রিসেট করা হয়েছে!'}

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'user_id' not in session:
        return {'message': 'লগইন করুন'}
    if 'file' not in request.files:
        return {'message': 'কোনো ফাইল নেই'}
    file = request.files['file']
    if file.filename == '':
        return {'message': 'ফাইল সিলেক্ট করুন'}
    
    user = User.query.get(session['user_id'])
    files = json.loads(user.files_data) if user.files_data else []
    
    file_data = base64.b64encode(file.read()).decode('utf-8')
    files.append({
        'name': file.filename,
        'size': len(file_data) * 0.75,
        'type': file.content_type,
        'data': file_data,
        'uploaded_at': datetime.utcnow().isoformat()
    })
    user.files_data = json.dumps(files)
    db.session.commit()
    return {'message': f'{file.filename} আপলোড সফল!'}

@app.route('/api/delete_file', methods=['POST'])
def delete_file():
    if 'user_id' not in session:
        return {'message': 'লগইন করুন'}
    filename = request.json.get('filename')
    user = User.query.get(session['user_id'])
    files = json.loads(user.files_data) if user.files_data else []
    files = [f for f in files if f['name'] != filename]
    user.files_data = json.dumps(files)
    db.session.commit()
    return {'message': f'{filename} ডিলিট করা হয়েছে!'}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        if not User.query.filter_by(email='admin@hoist.com').first():
            admin_user = User(name='Admin', email='admin@hoist.com')
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)