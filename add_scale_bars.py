import PhotoScan

accuracy = 0.00001

pairings = ['49_50', '50_51', '52_53', '53_54', '55_56', '57_58', '58_59', '60_61', '61_62', '63_64']

# define scale values, values are in meters.
scale_values = {}
scale_values['49_50'] = 0.50024
scale_values['50_51'] = 0.50058
scale_values['52_53'] = 0.25007
scale_values['53_54'] = 0.25034
scale_values['55_56'] = 0.25033
scale_values['57_58'] = 0.50027
scale_values['58_59'] = 0.50053
scale_values['60_61'] = 0.25004
scale_values['61_62'] = 0.25033
scale_values['63_64'] = 0.25034

doc = PhotoScan.app.document

for chunk in doc.chunks:

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
