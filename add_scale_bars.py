import PhotoScan

accuracy = 0.0001

pairings = ['1_3', '2_4', '49_50', '50_51', '52_53', '53_54', '55_56', '57_58', '58_59', '60_61', '61_62', '63_64']

scale_values = {
'49_50': 0.50024, '50_51': 0.50058,	'52_53': 0.25007, '53_54': 0.25034,
'55_56': 0.25033, '57_58': 0.50027,	'58_59': 0.50053, '60_61': 0.25004,
'61_62': 0.25033, '63_64': 0.25034, '1_3': 0.12500, '2_4': 0.12500 }

for chunk in PhotoScan.app.document.chunks:
	markers = {}
	for marker in chunk.markers:
		markers.update({marker.label.replace('target ',''): marker})

	scales = {}
	scalebars = {}
	for pair in pairings:
		a, b = pair.split('_')
		if a in markers.keys():
			scalebars[pair] = chunk.addScalebar(markers[a],markers[b])
			scalebars[pair].label = pair
			scalebars[pair].reference.accuracy = accuracy
			scalebars[pair].reference.distance = scale_values[pair]
