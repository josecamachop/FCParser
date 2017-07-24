#!/usr/bin/python

import argparse

def main():
	args = get_arguments()

	outstream = open(args.output, 'w')
	instream = open(args.infile, 'r')

	nlines = 0
	swapped = 0
	line = instream.readline()
	while line.strip():
		fieldList = line.split(',')
		sport = fieldList[args.srcport]
		dport = fieldList[args.dstport]
		sip = fieldList[args.srcip].strip()
		dip = fieldList[args.dstip].strip()
		protocol = fieldList[args.prot].strip()
		
		if (protocol=='TCP' or protocol=='UDP') and int(sport) < 1024 and int(dport) > 1024:
			fieldList[args.srcport] = dport
			fieldList[args.dstport] = sport
			fieldList[args.srcip] = dip
			fieldList[args.dstip] = sip
			newline = ','.join(fieldList)
			outstream.write(newline)
			swapped += 1
		else:
			outstream.write(line)
		
		nlines += 1
		line = instream.readline()
	
	outstream.close()
	instream.close()
	
	print "Swapping ports from << %s" %(args.infile)
	print "%d of %d lines swapped." %(swapped, nlines)
	print "Written >> %s" %(args.output)
	
	



def get_arguments():
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
	description='''Correct direction of the flows, following the heuristic: When source port is lower than 1024 and the protocol is UDP or TCP, swap ports.''')
	parser.add_argument('-o','--output', metavar='OUTPUT', default='result_swap.csv', help='Output file. Default: "<input>_swap.csv".')
	parser.add_argument('infile', metavar='FILE', help='Input data file (csv)')
	parser.add_argument('-s','--srcport', metavar='SRC_PORT_COL', type=int, required=True, help='Column (order) of the source port.')
	parser.add_argument('-d','--dstport', metavar='DST_PORT_COL', type=int, required=True, help='Column (order) of the destination port.')
	parser.add_argument('-i','--srcip', metavar='SRC_ADDR_COL', type=int, required=True, help='Column (order) of the source IP address.')
	parser.add_argument('-j','--dstip', metavar='DST_ADDR_COL', type=int, required=True, help='Column (order) of the destination IP address.')
	parser.add_argument('-p','--prot', metavar='PROT_COL', type=int, required=True, help='Column (order) of the protocol.')
	args = parser.parse_args()
	return args

if __name__ == "__main__":
	main()

