import os, sqlite3, secrets, json, calendar
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash

ROOT=os.path.dirname(os.path.abspath(__file__))
DB=os.environ.get('FINANCE_DB',os.path.join(ROOT,'finance.db'))
app=Flask(__name__)
app.secret_key=os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('HTTPS','0')=='1',MAX_CONTENT_LENGTH=2*1024*1024)

def conn():
 c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c

def init():
 with conn() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS cards(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,due INTEGER NOT NULL,closing INTEGER NOT NULL,card_limit INTEGER NOT NULL DEFAULT 0);
  CREATE TABLE IF NOT EXISTS entries(id INTEGER PRIMARY KEY,description TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('income','fixed','variable','daily','credit')),amount INTEGER NOT NULL CHECK(amount>=0),start_month TEXT NOT NULL,end_month TEXT,recurring INTEGER NOT NULL DEFAULT 0,category TEXT NOT NULL DEFAULT 'Outros',owner TEXT NOT NULL DEFAULT 'Família',card_id INTEGER REFERENCES cards(id) ON DELETE RESTRICT,installments INTEGER NOT NULL DEFAULT 1,created_by INTEGER REFERENCES users(id),source_key TEXT UNIQUE,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS payments(entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,month TEXT NOT NULL,PRIMARY KEY(entry_id,month));
  CREATE TABLE IF NOT EXISTS invoice_payments(card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,month TEXT NOT NULL,PRIMARY KEY(card_id,month));
  CREATE TABLE IF NOT EXISTS invitations(code TEXT PRIMARY KEY,expires TEXT NOT NULL,used INTEGER DEFAULT 0);
  CREATE TABLE IF NOT EXISTS budgets(category TEXT PRIMARY KEY,amount INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
init()

def seed_real_workbook():
 path=os.path.join(ROOT,'dados_planilha_real.json')
 if not os.path.exists(path):return
 data=json.load(open(path,encoding='utf8'))
 with conn() as c:
  if c.execute("SELECT 1 FROM settings WHERE key='seeded_real_workbook'").fetchone():return
  if c.execute('SELECT COUNT(*) FROM entries').fetchone()[0]:return
  ids={}
  for card in data['cards']:
   cur=c.execute('INSERT OR IGNORE INTO cards(name,due,closing,card_limit) VALUES(?,?,?,?)',(card['name'],card['due'],card['closing'],card['limit']))
   row=c.execute('SELECT id FROM cards WHERE name=?',(card['name'],)).fetchone();ids[card['name']]=row['id']
  for e in data['entries']:
   c.execute('INSERT OR IGNORE INTO entries(description,kind,amount,start_month,end_month,recurring,category,owner,card_id,installments,source_key) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(e['description'],e['kind'],e['amount'],e['start_month'],e.get('end_month'),e.get('recurring',0),e.get('category','Outros'),e.get('owner','Família'),ids.get(e.get('card')),e.get('installments',1),e['source']))
  for card,month in data['invoice_payments']:
   if card in ids:c.execute('INSERT OR IGNORE INTO invoice_payments(card_id,month) VALUES(?,?)',(ids[card],month))
  c.execute("INSERT INTO settings(key,value) VALUES('initial_balance',?)",(str(data['saldo_inicial']),))
  c.execute("INSERT INTO settings(key,value) VALUES('reference_month',?)",(data['reference_month'],))
  c.execute("INSERT INTO settings(key,value) VALUES('seeded_real_workbook','1')")
seed_real_workbook()

def csrf():
 if 'csrf' not in session:session['csrf']=secrets.token_urlsafe(24)
 return session['csrf']
app.jinja_env.globals['csrf']=csrf

def money(cents):return 'R$ '+f'{cents/100:,.2f}'.replace(',','X').replace('.',',').replace('X','.')
app.jinja_env.filters['money']=money

def parse_money(v):
 s=str(v or '0').strip().replace('R$','').replace(' ','')
 if ',' in s:s=s.replace('.','').replace(',','.')
 return round(float(s)*100)

def month_shift(m,n):
 y,mo=map(int,m.split('-'));a=y*12+mo-1+n;return f'{a//12:04d}-{a%12+1:02d}'

def months_between(start,end):
 a,b=map(int,start.split('-'));c,d=map(int,end.split('-'));return (c-a)*12+d-b

def login_required(fn):
 @wraps(fn)
 def wrap(*args,**kwargs):
  if 'uid' not in session:return redirect(url_for('login'))
  return fn(*args,**kwargs)
 return wrap

@app.before_request
def security():
 csrf()
 if request.method in ('POST','PUT','PATCH','DELETE'):
  if request.form.get('_csrf')!=session.get('csrf') and request.headers.get('X-CSRF-Token')!=session.get('csrf'):
   return 'Requisição não autorizada',403

@app.route('/setup',methods=['GET','POST'])
def setup():
 with conn() as c:
  if c.execute('SELECT COUNT(*) FROM users').fetchone()[0]:return redirect(url_for('login'))
 if request.method=='POST':
  name=request.form.get('name','').strip();email=request.form.get('email','').strip().lower();pwd=request.form.get('password','')
  if len(pwd)<10 or not name or '@' not in email:flash('Preencha os campos e use uma senha com 10 caracteres ou mais.');return redirect(url_for('setup'))
  with conn() as c:
   c.execute('INSERT INTO users(name,email,password) VALUES(?,?,?)',(name,email,generate_password_hash(pwd)))
  flash('Conta criada. Faça login.');return redirect(url_for('login'))
 return render_template('auth.html',title='Criar conta principal',mode='setup')

@app.route('/login',methods=['GET','POST'])
def login():
 with conn() as c:
  if not c.execute('SELECT COUNT(*) FROM users').fetchone()[0]:return redirect(url_for('setup'))
 if request.method=='POST':
  email=request.form.get('email','').strip().lower();pwd=request.form.get('password','')
  with conn() as c:u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
  if u and check_password_hash(u['password'],pwd):
   session.clear();session['uid']=u['id'];session['name']=u['name'];csrf();return redirect(url_for('home'))
  flash('E-mail ou senha incorretos.')
 return render_template('auth.html',title='Entrar no controle',mode='login')

@app.route('/logout',methods=['POST'])
@login_required
def logout():session.clear();return redirect(url_for('login'))

@app.route('/invite',methods=['GET','POST'])
def invite():
 code=request.args.get('code') or request.form.get('code','')
 with conn() as c:row=c.execute('SELECT * FROM invitations WHERE code=? AND used=0 AND expires>datetime("now")',(code,)).fetchone()
 if not row:return 'Convite inválido ou expirado.',400
 if request.method=='POST':
  name=request.form.get('name','').strip();email=request.form.get('email','').strip().lower();pwd=request.form.get('password','')
  if len(pwd)<10 or not name or '@' not in email:flash('Preencha os campos e use senha com 10 caracteres ou mais.');return redirect(url_for('invite',code=code))
  try:
   with conn() as c:
    c.execute('INSERT INTO users(name,email,password) VALUES(?,?,?)',(name,email,generate_password_hash(pwd)))
    c.execute('UPDATE invitations SET used=1 WHERE code=?',(code,))
  except sqlite3.IntegrityError:flash('Este e-mail já está cadastrado.');return redirect(url_for('invite',code=code))
  flash('Conta criada. Entre com seu e-mail e senha.');return redirect(url_for('login'))
 return render_template('auth.html',title='Aceitar convite familiar',mode='invite',code=code)

@app.route('/invite/new',methods=['POST'])
@login_required
def new_invite():
 code=secrets.token_urlsafe(22)
 with conn() as c:c.execute("INSERT INTO invitations(code,expires) VALUES(?,datetime('now','+7 days'))",(code,))
 flash('Link de convite (válido por 7 dias e um cadastro): '+request.host_url.rstrip('/')+url_for('invite',code=code))
 return redirect(url_for('home',tab='settings'))

def invoice_month(purchase_date,closing):
 # Purchase on/after closing day goes into following statement.
 y,m,d=map(int,purchase_date.split('-'));return month_shift(f'{y:04d}-{m:02d}',1 if d>=closing else 0)

def occurs(e,month):
 delta=months_between(e['start_month'],month)
 if delta<0:return False
 if e['kind']=='credit':return delta<e['installments']
 if e['end_month'] and month>e['end_month']:return False
 return bool(e['recurring']) or delta==0

def value_for(e,month):
 if e['kind']!='credit':return e['amount']
 n=e['installments'];base,extra=divmod(e['amount'],n)
 return base+(1 if months_between(e['start_month'],month)<extra else 0)

def monthly(c,month):
 all_entries=c.execute('SELECT e.*,cards.name AS card_name FROM entries e LEFT JOIN cards ON cards.id=e.card_id ORDER BY e.id DESC').fetchall()
 rows=[]
 for e in all_entries:
  if occurs(e,month):
   d=dict(e);d['month_value']=value_for(e,month);d['installment_no']=months_between(e['start_month'],month)+1;d['paid']=bool(c.execute('SELECT 1 FROM payments WHERE entry_id=? AND month=?',(e['id'],month)).fetchone());rows.append(d)
 return rows

@app.route('/')
@login_required
def home():
 month=request.args.get('month',date.today().strftime('%Y-%m'))
 if not request.args.get('month'):
  with conn() as c:
   ref=c.execute("SELECT value FROM settings WHERE key='reference_month'").fetchone()
   if ref:month=ref['value']
 try:datetime.strptime(month,'%Y-%m')
 except ValueError:month=date.today().strftime('%Y-%m')
 tab=request.args.get('tab','overview')
 with conn() as c:
  entries=monthly(c,month);cards=[dict(x) for x in c.execute('SELECT * FROM cards ORDER BY name')];budgets={r['category']:r['amount'] for r in c.execute('SELECT * FROM budgets')}
  months=[month_shift(month,n) for n in range(-5,7)]
  forecast=[]
  for m in months:
   rs=monthly(c,m);inc=sum(x['month_value'] for x in rs if x['kind']=='income');out=sum(x['month_value'] for x in rs if x['kind']!='income');forecast.append({'month':m,'income':inc,'out':out,'balance':inc-out})
  invoice_paid={(r['card_id'],r['month']) for r in c.execute('SELECT card_id,month FROM invoice_payments WHERE month=?',(month,))}
  initial_row=c.execute("SELECT value FROM settings WHERE key='initial_balance'").fetchone();initial_balance=int(initial_row['value']) if initial_row else 0
  paid_rows=c.execute('SELECT p.month,e.* FROM payments p JOIN entries e ON e.id=p.entry_id').fetchall()
  paid_invoices=c.execute('SELECT card_id,month FROM invoice_payments').fetchall()
  actual_balance=initial_balance+sum((1 if x['kind']=='income' else -1)*value_for(x,x['month']) for x in paid_rows if x['kind']!='credit')-sum(sum(value_for(e,r['month']) for e in c.execute('SELECT * FROM entries WHERE kind="credit" AND card_id=?',(r['card_id'],)).fetchall() if occurs(e,r['month'])) for r in paid_invoices)
 income=sum(e['month_value'] for e in entries if e['kind']=='income');expense=sum(e['month_value'] for e in entries if e['kind']!='income')
 card_data=[]
 for card in cards:
  purchases=[e for e in entries if e['kind']=='credit' and e['card_id']==card['id']]
  card_data.append({**card,'purchases':purchases,'total':sum(e['month_value'] for e in purchases),'paid':(card['id'],month) in invoice_paid,'months':[{'month':m,'total':sum(e['month_value'] for e in monthly(c,m) if e['kind']=='credit' and e['card_id']==card['id'])} for m in [month_shift(month,k) for k in range(12)]]})
 return render_template('index.html',month=month,prev=month_shift(month,-1),next=month_shift(month,1),tab=tab,entries=entries,cards=card_data,income=income,expense=expense,forecast=forecast,budgets=budgets,name=session.get('name'),today=date.today().isoformat(),actual_balance=actual_balance,initial_balance=initial_balance,categories=json.load(open(os.path.join(ROOT,'dados_planilha_real.json'),encoding='utf8'))['categories'])

@app.route('/entry',methods=['POST'])
@login_required
def entry():
 f=request.form;kind=f.get('kind','variable');card_id=f.get('card_id') or None
 if kind not in ('income','fixed','variable','daily','credit'):return 'Tipo inválido',400
 try:
  amount=parse_money(f.get('amount'));n=int(f.get('installments') or 1)
  if amount<=0 or not 1<=n<=360:raise ValueError()
  desc=f.get('description','').strip();dt=f.get('date','')
  datetime.strptime(dt,'%Y-%m-%d')
  if not desc or len(desc)>160:raise ValueError()
  recurring=int(f.get('recurring')=='on' and kind!='credit')
  end=f.get('end_month') or None
  if end and (len(end)!=7 or end<dt[:7]):raise ValueError()
  with conn() as c:
   if kind=='credit':
    card=c.execute('SELECT * FROM cards WHERE id=?',(card_id,)).fetchone()
    if not card:return 'Selecione um cartão.',400
    start=invoice_month(dt,card['closing'])
   else:start=dt[:7]
   c.execute('INSERT INTO entries(description,kind,amount,start_month,end_month,recurring,category,owner,card_id,installments,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(desc,kind,amount,start,end,recurring,f.get('category','Outros'),f.get('owner','Família'),card_id if kind=='credit' else None,n if kind=='credit' else 1,session['uid']))
  flash('Lançamento salvo.');return redirect(url_for('home',tab='cards' if kind=='credit' else 'overview',month=start))
 except (ValueError,TypeError,OverflowError):return 'Confira valor, data e parcelas.',400

@app.route('/entry/<int:entry_id>/edit',methods=['POST'])
@login_required
def edit_entry(entry_id):
 f=request.form
 try:
  amount=parse_money(f.get('amount'));kind=f.get('kind');n=int(f.get('installments') or 1)
  if amount<0 or kind not in ('income','fixed','variable','daily','credit') or not 1<=n<=360:raise ValueError()
  start=f.get('start_month','');datetime.strptime(start,'%Y-%m');end=f.get('end_month') or None
  if end and end<start:raise ValueError()
  card_id=f.get('card_id') or None
  with conn() as c:
   if kind=='credit' and not c.execute('SELECT 1 FROM cards WHERE id=?',(card_id,)).fetchone():return 'Cartão inválido',400
   c.execute('UPDATE entries SET description=?,kind=?,amount=?,start_month=?,end_month=?,recurring=?,category=?,owner=?,card_id=?,installments=? WHERE id=?',(f.get('description','').strip(),kind,amount,start,end,int(f.get('recurring')=='on' and kind!='credit'),f.get('category','Outros'),f.get('owner','Família'),card_id if kind=='credit' else None,n if kind=='credit' else 1,entry_id))
  flash('Lançamento atualizado.');return redirect(url_for('home',month=f.get('view_month') or start))
 except (ValueError,TypeError):return 'Dados inválidos.',400

@app.route('/entry/<int:entry_id>/delete',methods=['POST'])
@login_required
def delete_entry(entry_id):
 with conn() as c:c.execute('DELETE FROM entries WHERE id=?',(entry_id,))
 flash('Lançamento excluído.');return redirect(url_for('home',month=request.form.get('month') or date.today().strftime('%Y-%m')))

@app.route('/payment/<int:entry_id>',methods=['POST'])
@login_required
def payment(entry_id):
 month=request.form.get('month',date.today().strftime('%Y-%m'))
 with conn() as c:
  found=c.execute('SELECT 1 FROM payments WHERE entry_id=? AND month=?',(entry_id,month)).fetchone()
  if found:c.execute('DELETE FROM payments WHERE entry_id=? AND month=?',(entry_id,month))
  else:c.execute('INSERT INTO payments(entry_id,month) VALUES(?,?)',(entry_id,month))
 return redirect(url_for('home',month=month,tab=request.form.get('tab','overview')))

@app.route('/invoice/<int:card_id>/payment',methods=['POST'])
@login_required
def invoice_payment(card_id):
 month=request.form.get('month',date.today().strftime('%Y-%m'))
 with conn() as c:
  found=c.execute('SELECT 1 FROM invoice_payments WHERE card_id=? AND month=?',(card_id,month)).fetchone()
  if found:c.execute('DELETE FROM invoice_payments WHERE card_id=? AND month=?',(card_id,month))
  else:c.execute('INSERT INTO invoice_payments(card_id,month) VALUES(?,?)',(card_id,month))
 return redirect(url_for('home',tab='cards',month=month))

@app.route('/card',methods=['POST'])
@login_required
def card():
 try:
  name=request.form.get('name','').strip();due=int(request.form.get('due'));closing=int(request.form.get('closing'));limit=parse_money(request.form.get('limit') or '0')
  if not name or not 1<=due<=28 or not 1<=closing<=28 or limit<0:raise ValueError()
  with conn() as c:c.execute('INSERT INTO cards(name,due,closing,card_limit) VALUES(?,?,?,?)',(name,due,closing,limit))
  flash('Cartão cadastrado.')
 except (ValueError,sqlite3.IntegrityError):flash('Confira os dados ou verifique se o cartão já existe.')
 return redirect(url_for('home',tab='cards'))

@app.route('/card/<int:card_id>/edit',methods=['POST'])
@login_required
def edit_card(card_id):
 try:
  name=request.form.get('name','').strip();due=int(request.form.get('due'));closing=int(request.form.get('closing'));limit=parse_money(request.form.get('limit') or '0')
  if not name or not 1<=due<=28 or not 1<=closing<=28 or limit<0:raise ValueError()
  with conn() as c:c.execute('UPDATE cards SET name=?,due=?,closing=?,card_limit=? WHERE id=?',(name,due,closing,limit,card_id))
  flash('Cartão atualizado. Compras existentes mantêm o mês de início da fatura.')
 except (ValueError,sqlite3.IntegrityError):flash('Não foi possível atualizar o cartão.')
 return redirect(url_for('home',tab='cards'))

@app.route('/budget',methods=['POST'])
@login_required
def budget():
 try:
  category=request.form.get('category','Outros');amount=parse_money(request.form.get('amount'))
  if amount<0:raise ValueError()
  with conn() as c:c.execute('INSERT INTO budgets(category,amount) VALUES(?,?) ON CONFLICT(category) DO UPDATE SET amount=excluded.amount',(category,amount))
 except ValueError:flash('Valor inválido.')
 return redirect(url_for('home',tab='budget'))

@app.route('/backup')
@login_required
def backup():
 from io import BytesIO
 with conn() as c:
  data={table:[dict(x) for x in c.execute('SELECT * FROM '+table)] for table in ('cards','entries','payments','invoice_payments','budgets','settings')}
 return send_file(BytesIO(json.dumps(data,ensure_ascii=False,indent=2).encode()),as_attachment=True,download_name='backup-controle-caio-mariane.json',mimetype='application/json')

@app.route('/import-original',methods=['POST'])
@login_required
def import_original():
 path=os.path.join(ROOT,'gastos-originais.json')
 if not os.path.exists(path):flash('Arquivo original não encontrado.');return redirect(url_for('home'))
 rows=json.load(open(path,encoding='utf-8'));count=0
 with conn() as c:
  for n,(month,name,amount) in enumerate(rows):
   key=f'planilha-original-{n}'
   cur=c.execute('INSERT OR IGNORE INTO entries(description,kind,amount,start_month,recurring,category,owner,source_key,created_by) VALUES(?,?,?,?,?,?,?,?,?)',(name,'variable',round(float(amount)*100),month,0,'Não classificado','Família',key,session['uid']))
   count+=cur.rowcount
 flash(f'{count} lançamentos importados; nenhum foi marcado como pago. Revise classificações e possíveis duplicações com compras em cartões.')
 return redirect(url_for('home',tab='variable'))

if __name__=='__main__':
 app.run(host='127.0.0.1',port=int(os.environ.get('PORT','5000')),debug=False)
