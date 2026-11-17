// ============ LOGIN ============
function fazerLogin() {
    const user = document.getElementById('username').value;
    const pass = document.getElementById('password').value;
    if (user === 'admin' && pass === 'admin123') {
        document.getElementById('login-screen').classList.add('hidden');
        document.getElementById('app').classList.remove('hidden');
        iniciarSistema();
    } else {
        document.getElementById('login-error').innerText = "Usuário ou senha incorretos!";
    }
}

function fazerLogout() {
    document.getElementById('app').classList.add('hidden');
    document.getElementById('login-screen').classList.remove('hidden');
}

// ============ NAVEGAÇÃO ============
function iniciarSistema() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            const pageId = 'page-' + item.dataset.page;
            document.getElementById(pageId).classList.add('active');
            
            if (item.dataset.page === 'dispositivos') carregarDispositivos();
            if (item.dataset.page === 'dashboard') atualizarDashboard();
        });
    });
    
    atualizarDashboard();
    setInterval(atualizarDashboard, 15000);
}

// ============ DASHBOARD ============
async function atualizarDashboard() {
    try {
        const response = await fetch('/api/dispositivos');
        const result = await response.json();
        
        if (result.status === 'sucesso') {
            const dispositivos = result.dispositivos;
            document.getElementById('total-dispositivos').innerText = dispositivos.length;
            document.getElementById('total-online').innerText = 
                dispositivos.filter(d => d.status_conexao === 'ONLINE' || d.status_conexao === 'ALERTA').length;
            document.getElementById('total-alertas').innerText = 
                dispositivos.filter(d => d.status_conexao === 'ALERTA').length;
            
            // Gráfico do primeiro dispositivo
            if (dispositivos.length > 0) {
                await carregarGrafico(dispositivos[0].device_id);
            }
        }
    } catch (error) {
        console.error("Erro:", error);
    }
}

let chartInstance = null;
async function carregarGrafico(deviceId) {
    const response = await fetch(`/api/temperatura/historico?dispositivo_id=${deviceId}&limite=15`);
    const result = await response.json();
    
    if (result.status === 'sucesso') {
        const ctx = document.getElementById('tempChart').getContext('2d');
        if (chartInstance) chartInstance.destroy();
        
        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: result.dados.map(d => d.data_hora),
                datasets: [{
                    label: 'Temperatura (°C)',
                    data: result.dados.map(d => d.temperatura),
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { y: { beginAtZero: false } }
            }
        });
    }
}

// ============ DISPOSITIVOS ============
async function carregarDispositivos() {
    const response = await fetch('/api/dispositivos');
    const result = await response.json();
    const container = document.getElementById('lista-dispositivos');
    container.innerHTML = '';
    
    if (result.status === 'sucesso') {
        result.dispositivos.forEach(d => {
            const statusClass = `status-${d.status_conexao.toLowerCase()}`;
            
            // Luzes de status
            const wifiStatus = d.status_conexao === 'ONLINE' || d.status_conexao === 'ALERTA' ? 'green' : 'red';
            const dbStatus = d.ultima_leitura !== 'Nunca' ? 'green' : 'red';
            const sensorStatus = d.status_sensor === 'OK' ? 'green' : 
                                 d.status_sensor === 'FALHA' ? 'red' : 'yellow';
            
            const card = `
                <div class="dispositivo-card ${statusClass}">
                    <h3>${d.nome_freezer}</h3>
                    <div class="setor">${d.nome_setor} • ${d.device_id}</div>
                    
                    <div class="status-lights">
                        <div class="status-light">
                            <div class="light-dot ${wifiStatus}"></div>
                            <span>Wi-Fi</span>
                        </div>
                        <div class="status-light">
                            <div class="light-dot ${dbStatus}"></div>
                            <span>Banco</span>
                        </div>
                        <div class="status-light">
                            <div class="light-dot ${sensorStatus}"></div>
                            <span>Sensor</span>
                        </div>
                    </div>
                    
                    <div class="dispositivo-info">
                        <strong>Temp:</strong> ${d.ultima_temp !== null ? d.ultima_temp + '°C' : 'Sem leitura'}<br>
                        <strong>Faixa:</strong> ${d.temp_minima}°C - ${d.temp_maxima}°C<br>
                        <strong>Última conexão:</strong> ${d.ultima_conexao}
                    </div>
                </div>
            `;
            container.innerHTML += card;
        });
        
        if (result.dispositivos.length === 0) {
            container.innerHTML = '<p class="info">Nenhum dispositivo cadastrado. Vá em "Cadastrar Novo".</p>';
        }
    }
}

// ============ CADASTRO ============
async function cadastrarDispositivo() {
    const deviceId = document.getElementById('cad-device-id').value;
    const setor = document.getElementById('cad-setor').value;
    const freezer = document.getElementById('cad-freezer').value;
    const tempMin = document.getElementById('cad-temp-min').value;
    const tempMax = document.getElementById('cad-temp-max').value;
    
    if (!deviceId || !setor || !freezer) {
        document.getElementById('cadastro-mensagem').innerHTML = 
            '<p style="color:red">Preencha todos os campos!</p>';
        return;
    }
    
    try {
        const response = await fetch('/api/dispositivos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                device_id: deviceId,
                nome_setor: setor,
                nome_freezer: freezer,
                temp_minima: parseFloat(tempMin),
                temp_maxima: parseFloat(tempMax)
            })
        });
        
        const result = await response.json();
        
        if (result.status === 'sucesso') {
            document.getElementById('cadastro-mensagem').innerHTML = 
                '<p style="color:green">✅ Dispositivo cadastrado com sucesso!</p>';
            
            // Gerar QR Code
            const urlConfig = `${window.location.origin}/api/dispositivo/${deviceId}/config`;
            document.getElementById('qrcode-container').classList.remove('hidden');
            document.getElementById('qrcode').innerHTML = '';
            document.getElementById('qrcode-url').innerText = urlConfig;
            
            new QRCode(document.getElementById('qrcode'), {
                text: urlConfig,
                width: 200,
                height: 200
            });
            
            // Limpar formulário
            document.getElementById('cad-device-id').value = '';
            document.getElementById('cad-setor').value = '';
            document.getElementById('cad-freezer').value = '';
        } else {
            document.getElementById('cadastro-mensagem').innerHTML = 
                '<p style="color:red">Erro: ' + (result.detail || 'Desconhecido') + '</p>';
        }
    } catch (error) {
        document.getElementById('cadastro-mensagem').innerHTML = 
            '<p style="color:red">Erro de conexão!</p>';
    }
}