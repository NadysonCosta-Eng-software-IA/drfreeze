// --- 1. Lógica de Login Simples (Frontend Only para MVP) ---
function fazerLogin() {
    const user = document.getElementById('username').value;
    const pass = document.getElementById('password').value;

    // Simulação de autenticação (NÃO usar em produção real sem backend)
    if (user === 'admin' && pass === 'admin123') {
        document.getElementById('login-screen').classList.add('hidden');
        document.getElementById('dashboard-screen').classList.remove('hidden');
        iniciarDashboard();
    } else {
        document.getElementById('login-error').innerText = "Usuário ou senha incorretos!";
    }
}

function fazerLogout() {
    document.getElementById('dashboard-screen').classList.add('hidden');
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('username').value = '';
    document.getElementById('password').value = '';
    document.getElementById('login-error').innerText = '';
}

// --- 2. Lógica do Dashboard e Gráfico ---
let chartInstance = null;

async function iniciarDashboard() {
    await atualizarDados();
    // Atualiza automaticamente a cada 15 segundos
    setInterval(atualizarDados, 15000);
}

async function atualizarDados() {
    try {
        // Busca o histórico para o gráfico
        const responseHistorico = await fetch('/api/temperatura/historico?limite=15');
        const resultHistorico = await responseHistorico.json();

        // Busca o resumo (média + últimas 5 leituras)
        const responseResumo = await fetch('/api/temperatura/resumo');
        const resultResumo = await responseResumo.json();

        if (resultHistorico.status === 'sucesso' && resultResumo.status === 'sucesso') {
            const dados = resultHistorico.dados;
            
            // Atualiza o card de última temperatura
            if (dados.length > 0) {
                const ultima = dados[dados.length - 1];
                document.getElementById('ultima-temp').innerText = `${ultima.temperatura} °C`;
            }

            // Atualiza o card de temperatura média
            document.getElementById('temp-media').innerText = `${resultResumo.temperatura_media} °C`;

            // Atualiza a tabela de últimas 5 leituras
            atualizarTabelaLeituras(resultResumo.ultimas_leituras);

            // Prepara arrays para o Chart.js
            const labels = dados.map(d => d.data_hora);
            const temperaturas = dados.map(d => d.temperatura);

            renderizarGrafico(labels, temperaturas);
        }
    } catch (error) {
        console.error("Erro ao buscar dados:", error);
    }
}

// Nova função: Atualiza a tabela de últimas leituras
function atualizarTabelaLeituras(leituras) {
    const tbody = document.querySelector('#tabela-leituras tbody');
    tbody.innerHTML = ''; // Limpa a tabela

    leituras.forEach(leitura => {
        const row = tbody.insertRow();
        const cellData = row.insertCell(0);
        const cellTemp = row.insertCell(1);
        
        cellData.textContent = leitura.data_hora;
        cellTemp.textContent = `${leitura.temperatura} °C`;
        cellTemp.style.fontWeight = '600';
        cellTemp.style.color = '#007bff';
    });
}

function renderizarGrafico(labels, temperaturas) {
    const ctx = document.getElementById('tempChart').getContext('2d');

    if (chartInstance) {
        chartInstance.destroy(); // Destroi o gráfico antigo para atualizar
    }

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Temperatura (°C)',
                data: temperaturas,
                borderColor: '#007bff',
                backgroundColor: 'rgba(0, 123, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4 // Deixa a linha suave (curva)
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: false }
            }
        }
    });
}