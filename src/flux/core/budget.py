"""Hierarchical integer-micro ledger. Caller mutations run in BEGIN IMMEDIATE."""
from flux.knowledge.retrieval import digest
from flux.storage.workspace import now


class SharedBudget:
    def __init__(self, conn):
        self.conn=conn
        conn.executescript('''
          CREATE TABLE IF NOT EXISTS core_budget_accounts (
            id TEXT PRIMARY KEY, parent_id TEXT REFERENCES core_budget_accounts(id),
            cap INTEGER NOT NULL CHECK(cap>0), spent INTEGER NOT NULL DEFAULT 0,
            reserved INTEGER NOT NULL DEFAULT 0, unknown INTEGER NOT NULL DEFAULT 0,
            review_floor INTEGER NOT NULL DEFAULT 0, blocked INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS core_reservations (
            id TEXT PRIMARY KEY, account_id TEXT NOT NULL, scopes TEXT NOT NULL,
            request_hash TEXT NOT NULL, amount INTEGER NOT NULL, actual INTEGER,
            status TEXT NOT NULL, created_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS core_budget_conflicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, reservation_id TEXT NOT NULL,
            observation TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')
        conn.commit()
        with conn:
            if 'physical_key' not in {r[1] for r in conn.execute('PRAGMA table_info(core_reservations)')}:
                conn.execute("ALTER TABLE core_reservations ADD COLUMN physical_key TEXT NOT NULL DEFAULT ''")
                conn.execute('UPDATE core_reservations SET physical_key=id')
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS core_reservation_physical_key ON core_reservations(physical_key)')

    def account(self, ident, parent, cap, review_floor=0):
        row=self.conn.execute('SELECT * FROM core_budget_accounts WHERE id=?',(ident,)).fetchone()
        if row:return dict(row)
        self.conn.execute('INSERT INTO core_budget_accounts (id,parent_id,cap,review_floor) VALUES (?,?,?,?)',(ident,parent,cap,review_floor))
        return dict(self.conn.execute('SELECT * FROM core_budget_accounts WHERE id=?',(ident,)).fetchone())

    def ancestors(self, ident):
        rows,seen=[],set()
        while ident:
            if ident in seen:raise ValueError('Budget hierarchy cycle.')
            seen.add(ident)
            row=self.conn.execute('SELECT * FROM core_budget_accounts WHERE id=?',(ident,)).fetchone()
            if not row:raise ValueError('Budget account missing.')
            rows.append(dict(row));ident=row['parent_id']
        return rows

    def reserve(self, ident, account_id, amount, request, review=False):
        import json
        if not isinstance(amount,int) or isinstance(amount,bool) or amount<0:raise ValueError('Integer positive reservation required.')
        request_hash=digest({'account':account_id,'amount':amount,'request':request,'review':review})
        physical_key=request if isinstance(request,str) else digest(request)
        prior=self.conn.execute('SELECT * FROM core_reservations WHERE id=?',(ident,)).fetchone()
        if prior:
            if prior['request_hash']!=request_hash:raise ValueError('Reservation idempotency conflict.')
            return prior['status']
        if self.conn.execute('SELECT 1 FROM core_reservations WHERE physical_key=?',(physical_key,)).fetchone():raise ValueError('Physical request already reserved under another reservation ID.')
        scopes=self.ancestors(account_id)
        for account in scopes:
            free=account['cap']-account['spent']-account['reserved']-account['unknown']
            floor=0 if review else account['review_floor']
            if account['blocked']:return 'BLOCKED_RECONCILIATION'
            if amount+floor>free:return 'BLOCKED_BUDGET'
        self.conn.execute('INSERT INTO core_reservations (id,account_id,scopes,request_hash,amount,actual,status,created_at,physical_key) VALUES (?,?,?,?,?,?,?,?,?)',
                          (ident,account_id,json.dumps([a['id'] for a in scopes]),request_hash,amount,None,'active',now(),physical_key))
        for account in scopes:self.conn.execute('UPDATE core_budget_accounts SET reserved=reserved+? WHERE id=?',(amount,account['id']))
        return 'active'

    def settle(self, ident, actual=None):
        import json
        if actual is not None and (not isinstance(actual,int) or isinstance(actual,bool) or actual<0):raise ValueError('Actual cost must be nonnegative integer micros.')
        row=self.conn.execute('SELECT * FROM core_reservations WHERE id=?',(ident,)).fetchone()
        if not row:raise KeyError(ident)
        scopes=json.loads(row['scopes'])
        if row['status']=='settled':
            if actual==row['actual']:return 'settled'
            self.conn.execute('INSERT INTO core_budget_conflicts (reservation_id,observation,created_at) VALUES (?,?,?)',(ident,json.dumps({'actual':actual,'prior':row['actual']}),now()))
            for scope in scopes:self.conn.execute('UPDATE core_budget_accounts SET blocked=1 WHERE id=?',(scope,))
            return 'BLOCKED_RECONCILIATION'
        if row['status']=='held_unknown' and actual is None:return 'held_unknown'
        column='reserved' if row['status']=='active' else 'unknown'
        status='held_unknown' if actual is None else 'settled'
        for scope in scopes:
            self.conn.execute(f'UPDATE core_budget_accounts SET {column}={column}-? WHERE id=?',(row['amount'],scope))
            self.conn.execute('UPDATE core_budget_accounts SET '+('unknown=unknown+?' if actual is None else 'spent=spent+?')+' WHERE id=?',(row['amount'] if actual is None else actual,scope))
            account=self.conn.execute('SELECT * FROM core_budget_accounts WHERE id=?',(scope,)).fetchone()
            if account['spent']+account['reserved']+account['unknown']>account['cap']:
                self.conn.execute('UPDATE core_budget_accounts SET blocked=1 WHERE id=?',(scope,))
        self.conn.execute('UPDATE core_reservations SET status=?,actual=? WHERE id=?',(status,actual,ident))
        return status

    def revise(self, ident, cap):
        row=self.conn.execute('SELECT * FROM core_budget_accounts WHERE id=?',(ident,)).fetchone()
        if not row:raise KeyError(ident)
        if not isinstance(cap,int) or cap<row['spent']+row['reserved']+row['unknown'] or cap<=0:raise ValueError('Cap cannot hide committed costs.')
        conflicts=self.conn.execute("SELECT 1 FROM core_budget_conflicts c JOIN core_reservations r ON c.reservation_id=r.id WHERE r.scopes LIKE ?",('%"'+ident+'"%',)).fetchone()
        self.conn.execute('UPDATE core_budget_accounts SET cap=?,blocked=? WHERE id=?',(cap,int(bool(conflicts)),ident))
