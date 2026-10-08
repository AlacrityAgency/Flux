"""Explicit bounded source ingestion, versioned records and live-hash invalidation."""
from pathlib import Path
import re
from flux.knowledge.retrieval import digest
from flux.storage.workspace import clean_text, now

EXTENSIONS = {'.py','.md','.txt','.js','.css','.html','.toml','.yaml','.yml'}
EXCLUDED = {'var','build','dist','node_modules','experiments','tmp','logs','backups','attachments','retrieval-corpus','knowledge'}


class SourceIndex:
    def __init__(self, repo, workspace):
        self.repo, self.conn, self.workspace = repo, repo.conn, workspace
        self.conn.executescript('''
          CREATE TABLE IF NOT EXISTS knowledge_sources (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, path TEXT NOT NULL,
            revision INTEGER NOT NULL, content_hash TEXT NOT NULL, status TEXT NOT NULL,
            updated_at TEXT NOT NULL, UNIQUE(project_id,path));
          CREATE TABLE IF NOT EXISTS knowledge_chunks (
            ref TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES knowledge_sources(id),
            revision INTEGER NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
            evidence_type TEXT NOT NULL, content_hash TEXT NOT NULL);
        ''')
        self.conn.commit()

    def index(self, project_id, paths):
        project = self.workspace.get_project(project_id)
        if not project or project['archived']:
            raise ValueError('Active project required.')
        if not paths or len(paths) > 200:
            raise ValueError('Select between 1 and 200 explicit source files.')
        root = Path(project['path']).resolve()
        prepared = []
        for name in paths:
            path = (root/name).resolve()
            if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
                raise ValueError('Source must be a regular file inside the project.')
            relative = path.relative_to(root)
            if any(p.startswith('.') or p.lower() in EXCLUDED for p in relative.parts) or path.suffix.lower() not in EXTENSIONS:
                raise ValueError('Source file is excluded from ingestion.')
            if re.search(r'auth|credential|secret|password|private.key', path.name, re.I):
                raise ValueError('Sensitive source filename excluded.')
            if path.stat().st_size > 300_000:
                raise ValueError('Source exceeds 300 KB.')
            content = clean_text(path.read_text(encoding='utf-8'), 300_000)
            kind = 'test_definition' if 'tests' in relative.parts or path.name.startswith('test_') else 'code' if path.suffix != '.md' else 'source_document'
            prepared.append((relative.as_posix(),content,kind))
        with self.repo._lock, self.conn:
            self.workspace._memory_mutation_gate({project_id})
            for path, content, kind in prepared:
                old = self.conn.execute('SELECT * FROM knowledge_sources WHERE project_id=? AND path=?',(project_id,path)).fetchone()
                if old and old['content_hash'] == digest(content) and old['status'] == 'available':
                    continue
                ident = old['id'] if old else 'src_'+digest(project_id+'\n'+path)[:24]
                revision = old['revision']+1 if old else 1
                self.conn.execute('INSERT INTO knowledge_sources VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,content_hash=excluded.content_hash,status=excluded.status,updated_at=excluded.updated_at',
                                  (ident,project_id,path,revision,digest(content),'available',now()))
                self.conn.execute('DELETE FROM knowledge_chunks WHERE source_id=?',(ident,))
                # Complete line ranges, no truncated byte/token fragments.
                chunks, current, start = [], [], 1
                for line_no,line in enumerate(content.splitlines(keepends=True),1):
                    if current and sum(map(len,current))+len(line)>4000:
                        chunks.append((start,line_no-1,''.join(current)));current=[];start=line_no
                    current.append(line)
                if current:chunks.append((start,len(content.splitlines()),''.join(current)))
                for start,end,text in chunks:
                    ref=f'{ident}:{revision}:{start}'
                    self.conn.execute('INSERT INTO knowledge_chunks VALUES (?,?,?,?,?,?,?)',(ref,ident,revision,f'{path}:{start}-{end}',text,kind,digest(text)))
            self.workspace._invalidate_memory_sessions(project_id)
        return self.sources(project_id)

    def sources(self, project_id):
        return [dict(r) for r in self.conn.execute('SELECT * FROM knowledge_sources WHERE project_id=? ORDER BY path',(project_id,))]

    def records(self, project_id):
        project = self.workspace.get_project(project_id)
        if not project or project['archived']:return []
        root = Path(project['path']).resolve()
        records = []
        for source in self.sources(project_id):
            if source['status'] != 'available':continue
            path=(root/source['path']).resolve()
            try:
                valid=path.is_relative_to(root) and path.is_file() and path.stat().st_size<=300_000 and digest(clean_text(path.read_text(encoding='utf-8'),300_000))==source['content_hash']
            except (OSError,ValueError,UnicodeError):valid=False
            if not valid:
                with self.repo._lock,self.conn:
                    self.conn.execute("UPDATE knowledge_sources SET status='stale' WHERE id=?",(source['id'],))
                    self.workspace._invalidate_memory_sessions(project_id)
                continue
            for row in self.conn.execute('SELECT * FROM knowledge_chunks WHERE source_id=? AND revision=?',(source['id'],source['revision'])):
                records.append({**dict(row),'status':'verified','source_ref':source['path'],'source_hash':source['content_hash']})
        return records
