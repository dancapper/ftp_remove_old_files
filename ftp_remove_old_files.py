#!/usr/bin/python

## ftp_remove_old_files.py - a script to remove files older than x days from an FTP site, including subfolder search
##
## v0.2a June 2021, Dan Capper <dan@hopfulthinking.com>
## 
## FTP server must support the MLSD command
##
## ** W A R N I N G ** W A R N I N G ** W A R N I N G **
##
## THIS IS PROVIDED FOR ** EDUCATIONAL PURPOSES ONLY **
##
## THIS IS NOT REPEAT NOT INTENDED TO BE USED BY ANYONE IN ANY WAY, FOR ANY PURPOSE, UNDER ANY CIRCUMSTANCES 
##
## IT IS BY ITS VERY NATURE DESTRUCTIVE, ITS PURPOSE IS TO DESTROY
##
## IT MAY ** DESTROY YOUR DATA ** STAIN YOUR CARPETS AND SOFT FURNISHINGS ** CHEW YOUR CORDS AND REMOTES ** AND/OR ANY NUMBER OF OTHER UNPLEASANT THINGS
##
## IF YOU DISREGARD THIS WARNING YOU ARE ON YOUR OWN ** DON'T COME CRYING TO ME IF BAD THINGS HAPPEN

import sys
from ftplib import FTP
from datetime import datetime,date,timedelta
import syslog

FTP_USER = "user"
FTP_PASS = "password"
FTP_HOST = "localhost"
FTP_PATH = "/path/to/files"

MAX_AGE_DAYS = 	7 	# Max age in days, delete any files or folders older than this
DEBUG = 	False   # Write debug to syslog and stdout
GO_DEEP = 	True	# Check inside folders which are not expired for expired files, remove empty folders after deleting expired files inside them.
MAX_DEPTH =     6       # How deep will it search from the given path
FORCE_RMD =     False   # Still try to RMD a Directory even if we found it empty, not recommended with GO_DEEP enabled.
SAFE_MODE =     True    # This setting in theory makes for a dry run. Refer the warning above.

### With any luck, there will be no need to touch the rest ###

OLDEST = date.today() - timedelta(days=MAX_AGE_DAYS)

files_removed = 0
dirs_removed = 0
files_processed = 0
dirs_processed = 0
depth = 0
deepest = 0
oldest_file = date.today()

def log_info(str):
	print("INFO: ",str)
	syslog.syslog(syslog.LOG_INFO, str)

def log_debug(str):
	if DEBUG:
		print("DEBUG: ",str)
		syslog.syslog(syslog.LOG_DEBUG, str)

def log_warn(str):
	print("WARNING: ",str)
	syslog.syslog(syslog.LOG_WARNING, str)

def log_err(str):
	print("ERROR: ",str)
	syslog.syslog(syslog.LOG_ERR, str)
	sys.exit(str) 

def modify_date(file):
	modify = file[1]['modify']
	yyyy = int(modify[:4])
	mm = int(modify[4:6])
	dd = int(modify[6:8])
	return date(yyyy, mm, dd)

def is_expired(file):
	global oldest_file
	moddate=modify_date(file)
	if moddate <= oldest_file:
		oldest_file = moddate
	if moddate <= OLDEST:
		return True
	else:
		return False	

def is_file(file):
	if file[1]['type']=='file':
		return True
	else:
		return False

def is_dir(file):
	if file[1]['type']=='dir':
		return True
	else:
		return False

def set_depth(incr):
	global depth
	global deepest
	depth += incr
	if deepest < depth:
		deepest = depth
	
def process_file(file):
	global files_removed
	global dirs_removed
	global files_processed
	global dirs_processed
	count = 0
	deleted = 0

	if file[0] == '.':
		log_debug(f'Skipping {file[0]}')
	elif file[0] == '..':
		log_debug(f'Skipping {file[0]}')
	elif is_dir(file):
		if depth >= MAX_DEPTH:
			log_warn(f'Skipping {ftp.pwd()}/{file[0]} due to MAX_DEPTH {MAX_DEPTH} reached')
		elif is_expired(file) or GO_DEEP:
			log_debug(f'Entering Directory {ftp.pwd()}/{file[0]}')
			if chdir(file[0]):
				set_depth(1)
				filecount = process_dir()
				if chdir('..'):
					set_depth(-1)
				else:
					log_err(f"Cannot exit folder {ftp.pwd()}! Aborting!")
				if filecount[0] == 0 and ( FORCE_RMD or filecount[1] > 0 ):
					if SAFE_MODE:
						log_info(f'Would remove Directory {ftp.pwd()}/{file[0]} but SAFE_MODE is active')
						dirs_removed += 1
						deleted += 1
					else:
						log_info(f'Removing Directory {ftp.pwd()}/{file[0]}')
						try:
							ftp.rmd(file[0])
						except Exception as e:
							log_warn(f"Exception {e.__class__} removing Directory {file[0]}: {e}")
						else:
							log_debug(f'Successfully Removed Directory {ftp.pwd()}/{file[0]}')
							dirs_removed += 1
							deleted += 1
				elif filecount[0] == 0:
					log_debug(f'Directory {ftp.pwd()}/{file[0]} has {filecount[0]} Files but {filecount[1]} were removed - Not removing')

				else:
					log_debug(f'Directory {ftp.pwd()}/{file[0]} contains {filecount[0]} Files - Not removing')
			else:
				log_warn(f'Unable to change into {file[0]}, Moving on')
		else:
			log_debug(f'Skipping Directory {file[0]}')

		dirs_processed += 1	
		count +=1

	elif is_file(file): 
		if is_expired(file):
			if SAFE_MODE:
				log_info(f'Would delete File {ftp.pwd()}/{file[0]} but SAFE_MODE is set')
				files_removed += 1
				deleted += 1
			else:
				log_info(f'Deleting {ftp.pwd()}/{file[0]}')
				try:
					ftp.delete(file[0])
				except Exception as e:
					log_warn(f"Exception {e.__class__} deleting {file[0]}: {e}")
				else:
					log_debug(f'Successfully deleted file {ftp.pwd()}/{file[0]}')
					files_removed += 1
					deleted += 1
		else:
			log_debug(f'Skipping File {file[0]}')

		files_processed +=1
		count +=1
	return count,deleted

def chdir(dir):
	try:
		ftp.cwd(dir)
	except Exception as e:
		log_warn(f"Exception {e.__class__} changing into {dir}: {e}")	
		return False
	else:
		return True

def list_dir():
	try:
		filelist=ftp.mlsd()
	except Exception as e:
		log_err(f"Exception {e.__class__} listing {ftp.cwd()}: {e}")
	else:
		return filelist
	
def process_dir():
	log_debug(f'Processing {ftp.pwd()}')
	filelist = list_dir()
	orig_count = 0
	diff = 0
	for file in filelist:
		count, deleted = process_file(file)
		orig_count += count
		diff += deleted
	new_count = orig_count - diff
	log_debug(f'Processed {ftp.pwd()} - original count {orig_count}, new count {new_count}, deleted {diff}')
	return new_count, diff

## The main event

start_time = datetime.now()

log_info(f'Start processing at {start_time} - host: {FTP_HOST} path: {FTP_PATH} max depth: {MAX_DEPTH} Force RMD: {"enabled" if FORCE_RMD else "disabled"} Go Deep: {"enabled" if GO_DEEP else "disabled"}')
log_info('SAFE_MODE active - What''s wrong McFly... Chicken?' if SAFE_MODE else 'SAFE_MODE inactive - Going in Weapons Hot')
log_debug('Debug is Enabled') 

try:
	ftp=FTP(FTP_HOST)
except Exception as e:
	log_err(f"Exception {e.__class__} Connecting to {FTP_HOST}: {e}")

try: 
	ftp.login(FTP_USER,FTP_PASS)
except Exception as e:
	log_err(f"Exception {e.__class__} Logging in to {FTP_HOST} as {FTP_USER}: {e}")
else:
	log_info(f'Successfully connected to {FTP_HOST} in {(datetime.now() - start_time).total_seconds()} seconds.')

try:
	ftp.cwd(FTP_PATH)
except Exception as e:
	log_err(f"Exception {e.__class__} changng to {FTP_PATH}: {e}")

process_dir()

log_info(f'Completed processing {dirs_processed} {"dir" if dirs_processed == 1 else "dirs"} and {files_processed} {"file" if files_processed == 1 else "files"} in {(datetime.now() - start_time).total_seconds()} seconds. Removed {files_removed} {"file" if files_removed == 1 else "files"} and {dirs_removed} {"dir" if dirs_removed == 1 else "dirs"}. Deepest directory {deepest} of {MAX_DEPTH}. Oldest file found {oldest_file}.')
