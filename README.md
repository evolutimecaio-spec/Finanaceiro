# Controle Caio & Mariane

Sistema de controle financeiro familiar com cartões, faturas, gastos fixos, variáveis, diários e projeções.

## Instalação

O pacote completo foi entregue em arquivo ZIP no ChatGPT. Extraia os arquivos e envie `app.py`, `templates/` e `static/` a este repositório.

**IMPORTANTE:** este repositório está PÚBLICO. Não envie os arquivos `finance.db`, `dados_planilha_real.json`, `gastos-originais.json` nem planilhas contendo valores reais. Os dados devem ser importados em ambiente privado, com banco persistente e backups.

Para executar o código completo localmente: `pip install -r requirements.txt` e `python app.py`.

Para hospedar: configure HTTPS, SECRET_KEY, FINANCE_DB em volume persistente e inicie com `gunicorn app:app --bind 0.0.0.0:$PORT`.

A aplicação ainda não está publicada e requer testes antes do uso diário.