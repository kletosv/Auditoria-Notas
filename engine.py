import csv, hashlib, json, re, sqlite3, unicodedata
from pathlib import Path
import fitz

DB="auditoria.sqlite3"
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
    data={}
    if not Path(path).exists(): return data
    with open(path,encoding='utf-8-sig',newline='') as f:
        sample=f.read(4096);f.seek(0)
        delim=';' if sample.count(';')>sample.count(',') else ','
        for r in csv.DictReader(f,delimiter=delim):
            normalized={normalize(k).strip():v for k,v in r.items() if k}
            mat=re.sub(r'\D','',normalized.get('MATRICULA',''))
            if mat: data[mat]=normalized
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
                # Contexto curto: cabeçalhos de ato e palavras-chave não garantem vínculo linha a linha.
                for j,line in enumerate(norm):
                    mats=set(MAT.findall(line))
                    if not mats:continue
                    context=' '.join(norm[max(0,j-14):min(len(lines),j+4)])
                    kinds=[k for k,pattern in KEYWORDS.items() if re.search(pattern,context)]
                    if not kinds:continue
                    yrs=sorted(set(YEARS.findall(context)))
                    excerpt=' | '.join(lines[max(0,j-2):min(len(lines),j+3)])[:850]
                    for mat in mats:
                        r=base.get(mat,{})
                        name=r.get('SERVIDOR','')
                        for kind in kinds:
                            for yr in (yrs or ['INDETERMINADO']):
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
