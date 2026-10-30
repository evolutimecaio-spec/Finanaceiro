# Controle Caio & Mariane — versão web com dados reais

Esta versão inclui **13 cartões distintos e 39 lançamentos extraídos do arquivo XLSM fornecido** (incluindo registros de gastos fixos, variáveis e compras). O banco `finance.db` está preenchido, mas **não há contas de usuário criadas**. A primeira pessoa a abrir `/setup` cria a conta principal; a segunda recebe um convite na aba Configurações.

## Executar localmente

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Acesse `http://127.0.0.1:5000/setup`.

## Colocar na internet

Publique em um serviço que suporte **Python/Flask e armazenamento persistente**. Configure `SECRET_KEY` como segredo aleatório fixo, `HTTPS=1`, `FINANCE_DB` como caminho de um **volume persistente** que contenha uma cópia do `finance.db`, e o comando de inicialização `gunicorn app:app --bind 0.0.0.0:$PORT`. Sem volume persistente, o banco pode desaparecer após um redeploy. Configure HTTPS e acesso restrito antes de usar dados reais. Faça backups do banco e do JSON em Configurações.

**Não use hospedagem pública de arquivos estáticos**, porque o sistema precisa de backend e banco de dados. Nunca envie o arquivo `finance.db` para repositório público: contém dados financeiros familiares.

## Atenção aos dados importados

- A planilha fornecida tinha 14 cartões cadastrados, 39 lançamentos preenchidos e **nenhuma receita preenchida**.
- Saldo inicial da planilha: R$ 0,01. Confirme antes de interpretar o saldo real.
- Datas de início de gastos fixos eram provisórias e as datas de vencimento de gastos variáveis estavam vazias; o sistema preservou o mês de referência 11/2026, mas **não inventou vencimentos específicos**.
- Gastos variáveis sem valor foram mantidos como R$ 0,00 para conferência; não entram nos totais até serem preenchidos.
- A planilha também tinha faturas listadas automaticamente: elas foram **recalculadas a partir das compras**, sem importar a listagem como despesas duplicadas.
- As compras no cartão estão vinculadas ao mês da primeira fatura conforme a planilha, não recalculadas pelo dia do fechamento. As próximas parcelas se encerram automaticamente.
- Pagamentos não foram presumidos: lançamentos e faturas permanecem pendentes até você marcar como pagos.

**Estado de validação:** código compilado sintaticamente e dados conferidos no SQLite. Não foi possível executar testes de interface nesta sessão porque o ambiente não tem Flask instalado nem acesso à rede para instalá-lo. Faça teste de uso antes de confiar como único registro financeiro.
