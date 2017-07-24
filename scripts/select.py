#!/usr/bin/env python

import argparse
from datetime import datetime

def main():
	args = get_arguments()
	col = int(args.col)

	print "<< <input_file_name> (<selected_lines> / <total_lines>)"
	print "----------------------------------------------------"


	fileCount = 0
	for inpath in args.files:
		outpath = args.outdir + "selected_" + inpath
		outstream = open(outpath, 'w')
		instream = open(inpath, 'r')
		fileCount += 1
		lineCount = 0
		selectCount = 0
		line = instream.readline()
		while line:
			lineCount += 1
			fieldList = line.split(',')
			value = fieldList[col]
			if value == args.val:
				outstream.write(line)
				selectCount += 1
			line = instream.readline()

		instream.close()
		outstream.close()
		
		print "#%s / %s >> %s (%d / %d)" %(fileCount, len(args.files), outpath, selectCount, lineCount)
				
	print "----------------------------------------------------"
	print "%d input files" %(fileCount)
	
	
	


def get_arguments():
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
	description='''Select the rows that match a given field value.''')
	parser.add_argument('-o','--outdir', metavar='OUTDIR', default='./', help='Output directory. Default: "./"')
	parser.add_argument('-c','--col', metavar='COLUMN', default=0, help='Column (order) of the field to match. Default: 0')
	parser.add_argument('-v','--val', metavar='VALUE', help='Value of the match.')

	parser.add_argument('files', metavar='FILE', nargs='+',help='Input data files (CSV format)')
	args = parser.parse_args()
	return args

if __name__ == "__main__":
	main()

