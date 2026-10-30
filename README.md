# Controle Caio & Mariane — versão independente

Aplicativo web familiar, com tema escuro, banco de dados SQLite, acesso individual por senha e dados compartilhados entre os usuários cadastrados. Não depende do Floot nem tem limite diário de edição do código.

## Instalação no computador (Windows)

1. Instale Python 3.11 ou superior.
2. Abra o terminal na pasta do projeto.
3. Execute `py -m pip install -r requirements.txt`.
4. Defina uma chave secreta permanente no ambiente: PowerShell: `$env:SECRET_KEY = 'COLOQUE_AQUI_UMA_CHAVE_LONGA_ALEATORIA_E_PERMANENTE'`. Para uso contínuo, configure-a nas variáveis de ambiente do servidor.
5. Execute `py app.py`.
6. Abra `http://127.0.0.1:5000` e crie a conta principal.
7. Em **Configurações**, gere um convite para Mariane.

**Importante:** neste modo local, o sistema só pode ser acessado pelo computador que está executando o servidor. Para compartilhar pela internet, hospede o projeto em um serviço que suporte Python e **armazenamento persistente** (disco/volume para `finance.db`), configure `SECRET_KEY` fixa, `HTTPS=1`, e use HTTPS. Não exponha o servidor de desenvolvimento Flask diretamente à internet: execute-o com servidor WSGI de produção (por exemplo, `waitress-serve --listen=0.0.0.0:5000 app:app` em Windows ou `gunicorn app:app` em Linux, com dependência instalada). A disponibilidade e custos da hospedagem dependem do provedor.

## Dados da planilha

O arquivo `gastos-originais.json` contém os registros extraídos da planilha anterior. Em **Configurações > Importar gastos originais**, clique uma vez para importá-los. A importação é idempotente por registro de origem; não marca despesas como pagas e não deduz cartões/parcelas automaticamente. Revise classificações e duplicações.

## Cálculos

- Cartões: valor **total** da compra dividido pelo número de parcelas, distribuindo centavos sem perder valores. Fechamento: compra no dia de fechamento ou depois entra na fatura seguinte.
- Contas fixas/variáveis e receitas: únicas ou recorrentes mensalmente; data final opcional.
- Fatura: soma das parcelas ativas de cada cartão no mês; pagamento de fatura é separado de pagamentos de contas, para evitar dupla contagem.
- Saldo exibido é **previsto**, não saldo bancário real.

## Segurança e backup

- Senhas armazenadas como hashes, sessões com cookies HttpOnly e proteção CSRF em formulários.
- Convites únicos válidos por 7 dias.
- O banco `finance.db` contém dados financeiros privados: faça backup regularmente, proteja o servidor e **não publique esse arquivo**.
- Em **Configurações**, exporte backup JSON. A importação de backup completo ainda não foi implementada; preserve também cópias do arquivo `finance.db` com o aplicativo parado.
- A versão atual não tem recuperação de senha por e-mail, autenticação multifator ou sincronização offline.
- O banco é compartilhado entre todas as contas criadas por convite. Não compartilhe convites com terceiros.

## Funcionalidades

Painel com receitas, despesas, saldo previsto, gráficos; gastos fixos e variáveis; cartões e compras parceladas; faturas por mês; orçamento por categoria; previsão futura; edição/exclusão; marcação de pagamentos; backup; importação da planilha.
