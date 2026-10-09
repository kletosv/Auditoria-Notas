import csv, hashlib, json, re, sqlite3, unicodedata
from pathlib import Path
import fitz

DB="auditoria.sqlite3"
ENGINE_VERSION="2.0-contexto-adi"
KEYWORDS={"RETIFICACAO":r"RETIFIC|ONDE CONSTA|PASSE A CONSTAR|CORRIG",
          "INCLUSAO":r"INCLU[SÍI]|INCLUIR|ACRESCENT",
          "ANULACAO":r"ANULA|TORNAR SEM EFEITO|DESCONSIDER|EXCLUIR|CANCELA"}
YEARS=re.compile(r"\b20(?:19|20|21|22|23|24|25)\b")
MAT=re.compile(r"(?<!\d)\d{7,11}(?!\d)")
def normalize(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(s).upper()) if not unicodedata.combining(c))
def connect():
    con=sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS docs (id TEXT PRIMARY KEY, name TEXT, numero INTEGER, tipo TEXT, pages INTEGER DEFAULT 0, done_pages INTEGER DEFAULT 0, status TEXT DEFAULT 'PENDENTE', error TEXT DEFAULT '')")
    con.execute("CREATE TABLE IF NOT EXISTS hits (doc TEXT, page INTEGER, tipo TEXT, matricula TEXT, servidor TEXT, exercicio TEXT, base_valor TEXT, trecho TEXT, situacao TEXT DEFAULT 'CANDIDATO - REVISAR', UNIQUE(doc,page,tipo,matricula,exercicio,trecho))")
    con.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    version=con.execute("SELECT value FROM meta WHERE key='engine_version'").fetchone()
    if version is None or version[0]!=ENGINE_VERSION:
        # Candidatos antigos são inválidos; não reaproveitar resultados da heurística anterior.
        con.execute("DELETE FROM hits")
        con.execute("DELETE FROM docs")
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES ('engine_version',?)",(ENGINE_VERSION,))
    con.commit()
    return con
def identity(path):
    name=path.name
    m=re.search(r"(?<!\d)(1[012][.\s]?\d{3})(?!\d)",name)
    num=int(re.sub(r"\D","",m.group(1))) if m else 99999
    typ='SUPLEMENTO' if re.search('SUP',name,re.I) else ('EXTRA' if re.search('EXTRA',name,re.I) else 'PRINCIPAL')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    return digest,num,typ
def load_base_csv(path):
    """Carrega CSV Excel (UTF-8, UTF-16, Windows-1252) sem modificar a base."""
    import io
    path=Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Base Geral não encontrada: {path}")
    raw=path.read_bytes()
    if not raw:
        raise ValueError("Arquivo CSV da Base Geral está vazio")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings=("utf-16",)
    elif raw.startswith(b"\xef\xbb\xbf"):
        encodings=("utf-8-sig",)
    else:
        encodings=("utf-8-sig", "cp1252", "latin-1")
    content=None
    for encoding in encodings:
        try:
            content=raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        raise ValueError("Não foi possível identificar a codificação do CSV")
    # Excel brasileiro costuma usar ;, mas também aceita , e tab.
    header=next((line for line in content.splitlines() if line.strip()), "")
    delimiter=max((";", ",", "\t"), key=header.count)
    if delimiter not in header:
        raise ValueError("Separador do CSV não identificado")
    reader=csv.DictReader(io.StringIO(content, newline=""), delimiter=delimiter)
    headers={normalize(h).strip().lstrip("\ufeff") for h in (reader.fieldnames or []) if h}
    if not {"MATRICULA", "SERVIDOR"}.issubset(headers):
        raise ValueError("CSV inválido: abra a aba Base Geral antes de salvar; colunas MATRÍCULA e SERVIDOR são obrigatórias")
    data={}
    for row in reader:
        normalized={normalize(k).strip():v for k,v in row.items() if k}
        mat=re.sub(r"\D", "", normalized.get("MATRICULA", "") or "")
        if mat:
            data[mat]=normalized
    if not data:
        raise ValueError("Nenhuma matrícula válida foi encontrada no CSV")
    return data
def scan_one(path,base):
    con=connect()
    digest,num,typ=identity(path)
    old=con.execute("SELECT status,done_pages FROM docs WHERE id=?",(digest,)).fetchone()
    if old and old[0]=='CONCLUIDO':con.close();return 'já concluído'
    con.execute("INSERT OR IGNORE INTO docs (id,name,numero,tipo) VALUES (?,?,?,?)",(digest,path.name,num,typ))
    con.commit()
    try:
        with fitz.open(path) as pdf:
            count=len(pdf)
            con.execute("UPDATE docs SET pages=?,status='EM ANALISE',error='' WHERE id=?",(count,digest));con.commit()
            start=old[1] if old else 0
            for i in range(start,count):
                raw=pdf[i].get_text(sort=True)
                lines=[x.strip() for x in raw.splitlines() if x.strip()]
                norm=[normalize(x) for x in lines]
                # Filtro conservador: exigir contexto explícito de avaliação individual
                # E matrícula existente na base. Não usar anos soltos da página.
                adi_context=re.compile(r"AVALIACAO\s+(?:DE\s+)?DESEMPENHO|\bADI\b|\bPGDI\b|NOTAS?\s+(?:DA\s+)?AVALIACAO|RESULTADO\s+(?:DA\s+)?AVALIACAO")
                negative=re.compile(r"ORCAMENTARI|CONTRATO|LICITACAO|EMPENHO|PREGAO|TERMO ADITIVO")
                for j,line in enumerate(norm):
                    mats={m for m in MAT.findall(line) if m in base}
                    if not mats: continue
                    # A janela limitada evita associar uma retificação de outro ato.
                    before=' '.join(norm[max(0,j-10):j+1])
                    after=' '.join(norm[j:min(len(norm),j+3)])
                    context=before+' '+after
                    if not adi_context.search(context):continue
                    if negative.search(context):continue
                    kinds=[k for k,pattern in KEYWORDS.items() if re.search(pattern,before)]
                    if not kinds:continue
                    # Só atribuir exercício quando estiver na própria linha;
                    # caso contrário, manter indeterminado para revisão humana.
                    yrs=sorted(set(YEARS.findall(line))) or ['INDETERMINADO']
                    excerpt=' | '.join(lines[max(0,j-10):min(len(lines),j+3)])[:1400]
                    for mat in mats:
                        r=base[mat]
                        name=r.get('SERVIDOR','')
                        for kind in kinds:
                            for yr in yrs:
                                value=r.get('NOTA '+yr,'') if yr!='INDETERMINADO' else ''
                                con.execute("INSERT OR IGNORE INTO hits(doc,page,tipo,matricula,servidor,exercicio,base_valor,trecho) VALUES(?,?,?,?,?,?,?,?)",(digest,i+1,kind,mat,name,yr,str(value),excerpt))
                con.execute("UPDATE docs SET done_pages=? WHERE id=?",(i+1,digest))
                con.commit()
            con.execute("UPDATE docs SET status='EXTRACAO CONCLUIDA - REVISAR' WHERE id=?",(digest,))
            con.commit()
        return 'extração concluída, pendente de validação'
    except Exception as e:
        con.execute("UPDATE docs SET status='ERRO',error=? WHERE id=?",(str(e),digest));con.commit()
        return f'erro: {e}'
    finally:con.close()
def run_folder(folder,base_csv):
    paths=sorted(Path(folder).glob('*.pdf'),key=lambda p:(identity(p)[1],0 if identity(p)[2]=='PRINCIPAL' else 1,p.name))
    base=load_base_csv(base_csv)
    seen=set()
    for path in paths:
        h,_,_=identity(path)
        if h in seen:continue
        seen.add(h)
        yield path.name,scan_one(path,base)
