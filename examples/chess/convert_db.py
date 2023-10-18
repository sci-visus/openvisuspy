import json
import logging
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
						lockfile TEXT,
						insert_time timestamp NOT NULL, 
						conversion_start timestamp,
						conversion_end timestamp,
						conversion_failed timestamp 
				)
				""")
				self.conn.commit()

		# close
		def close(self):
				self.conn.close()
				self.conn = None

		# pushPendingConvert
		def pushPendingConvert(self, group, name, src, dst, compression="zip", arco="8mb", metadata=[]):
				# TODO: if multiple converters?
				self.conn.executemany(
						"INSERT INTO datasets ('group', name, src, dst, compression, arco, metadata, insert_time) values(?,?,?,?,?,?,?,?)",
						[
								(group, name, src, dst, compression, arco, json.dumps(metadata), datetime.now())
						])
				self.conn.commit()

		def setLockFile(self, id, lockfile):
				self.conn.execute("UPDATE datasets set lockfile=? where id=?", (lockfile, id))
				self.conn.commit()

		# toDict
		def toDict(self, row):
				if row is None: return None
				ret = {k: row[k] for k in row.keys()}
				ret["metadata"] = json.loads(ret["metadata"])
				return ret

		# popPendingConvert
		def popPendingConvert(self):
				data = self.conn.execute(
						"SELECT * FROM datasets WHERE conversion_start is NULL AND conversion_end is NULL order by id ASC LIMIT 1")
				ret = self.toDict(data.fetchone())
				if ret is None: return None
				ret["conversion_start"] = str(datetime.now())
				data = self.conn.execute("UPDATE datasets SET conversion_start=? where id=?",
																 (ret["conversion_start"], ret["id"],))
				self.conn.commit()
				return ret

		def getPendingConverts(self):
				for pending in self.conn.execute(
								f"select * from datasets where conversion_start is null and conversion_end is null and conversion_failed is null"):
						yield self.toDict(pending)

		def getFailedConverts(self):
				for failed in self.conn.execute(
								f"select * from datasets WHERE conversion_start is not NULL and conversion_end is NULL and conversion_failed is null"):
						yield self.toDict(failed)

		# Mark conversion as failed by setting the conversion_failed timestamp
		def markFailed(self, id):
				self.conn.execute("UPDATE datasets set conversion_failed=? where id=?", (str(datetime.now()), id))
				self.conn.commit()

		def markStarted(self, record_id):
				self.conn.execute("UPDATE datasets SET conversion_start=? where id=?", (str(datetime.now()), record_id))
				self.conn.commit()

		# setConvertDone
		def setConvertDone(self, specs):
				specs["conversion_end"] = str(datetime.now())
				data = self.conn.execute("UPDATE datasets SET conversion_end=? where id=?",
																 (specs["conversion_end"], specs["id"],))
				self.conn.commit()

		# getRecords
		def getRecords(self, where):
				for it in self.conn.execute(f"SELECT * FROM datasets {where} ORDER BY id ASC"):
						yield self.toDict(it)

		# getRecordById
		def getRecordById(self, id):
				data = self.conn.execute("SELECT * FROM datasets WHERE id=?", [id])
				return self.toDict(data.fetchone())

