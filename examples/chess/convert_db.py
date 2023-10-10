import os,sys,logging,json
import sqlite3 
from datetime import datetime

logger = logging.getLogger("nsdf-convert")

# ///////////////////////////////////////////////////////////////////////
class ConvertDb:

	# constructor
	def __init__(self, db_filename):
		
		self.conn = sqlite3.connect(db_filename)
		self.conn.row_factory = sqlite3.Row
		self.conn.execute("""
		CREATE TABLE IF NOT EXISTS datasets (
			id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
			'group' TEXT NOT NULL, 
			name TEXT NOT NULL,
			src TEXT NOT NULL,
			dst TEXT NOT NULL,
			compression TEXT,
			arco TEXT,
			metadata TEXT,
			insert_time timestamp NOT NULL, 
			conversion_start timestep ,
			conversion_end   timestamp 
		)
		""")
		self.conn.commit()

	# close
	def close(self):
		self.conn.close()
		self.conn=None

	# pushPendingConvert
	def pushPendingConvert(self, group, name, src, dst, compression="zip", arco="modvisus", metadata=[]):
		# TODO: if multiple converters?
		self.conn.executemany("INSERT INTO datasets ('group', name, src, dst, compression, arco, metadata, insert_time) values(?,?,?,?,?,?,?,?)",[
			(group, name, src, dst, compression, arco, json.dumps(metadata), datetime.now())
		])
		self.conn.commit()

	# popPendingConvert
	def popPendingConvert(self):
		data = self.conn.execute("SELECT * FROM datasets WHERE conversion_start is NULL AND conversion_end is NULL order by id ASC LIMIT 1")
		row=data.fetchone()
		if row is None: return None
		row={k:row[k] for k in row.keys()}
		row["metadata"]=json.loads(row["metadata"])
		row["conversion_start"]=str(datetime.now())
		data = self.conn.execute("UPDATE datasets SET conversion_start==? where id=?",(row["conversion_start"],row["id"], ))
		self.conn.commit()
		return row

	# setConvertDone
	def setConvertDone(self, row):
		row["conversion_end"]=str(datetime.now())
		data = self.conn.execute("UPDATE datasets SET conversion_end==? where id=?",(row["conversion_end"],row["id"], ))
		self.conn.commit()

	# getAllRecords
	def getAllRecords(self):
		for row in self.conn.execute("SELECT * FROM datasets ORDER BY id ASC"):
			yield {k:row[k] for k in row.keys()}

	# getRecordById
	def getRecordById(self,id):
		row=self.conn.execute("SELECT * FROM datasets WHERE id=?",[id])[0]
		return {k:row[k] for k in row.keys()}

	# getMaybeFailed 
	def getMaybeFailed(self):
		for row in self.conn.execute("SELECT * FROM datasets WHERE conversion_start is not NULL and conversion_end is NULL ORDER BY id ASC"):
			yield {k:row[k] for k in row.keys()}

	# getConverted
	def getConverted(self):
		for row in self.conn.execute("SELECT * FROM datasets WHERE conversion_end is not NULL ORDER BY id ASC"):
			yield {k:row[k] for k in row.keys()}

		
