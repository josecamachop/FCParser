#!/usr/bin/python

import argparse

def main():
	args = get_arguments()

	outstream = open(args.output, 'w')
	instream = open(args.infile, 'r')

	lineID = 1
	line = instream.readline()
	while line.strip():
		newline = line.strip() + ',' + str(lineID) + '\n'
		outstream.write(newline)
		lineID += 1
		line = instream.readline()
	
	outstream.close()
	instream.close()
	
	
	print "Adding IDs to << %s" %(args.infile)
	print "%d lines modified." %(lineID)
	print "Written >> %s" %(args.output)
	
	



def get_arguments():
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
	description='''Add flow ID to a csv file, a last argument.''')
	parser.add_argument('-o','--output', metavar='OUTPUT', default='data_result.dat', help='Output file. Default: "data_result.dat".')
	parser.add_argument('infile', metavar='FILE', help='Input data file (csv)')
	args = parser.parse_args()
	return args

if __name__ == "__main__":
	main()

