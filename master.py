import PhotoScan
import os

# Specify folder of unique identifier.
# Files must be in the following locations:
# [identifier]
#   \JPG\
#     \SIDEA\ -- location of jpegs for top view
#     \SIDEB\ -- location of jpegs for bottom view
#   \PROCESSING\ -- location to be used for psx file

doc = PhotoScan.app.document
server_ip = ''
shared_root = ''
images_folder = 'JPG'
process_folder = 'PROCESSING'
# TODO: Add support for non-network processing.
mode = 'network'

def set_mode(md):
	global mode
	if md == 'check':
		PhotoScan.app.messageBox(mode)
	elif md == 'local':
		PhotoScan.app.messageBox("Local mode not implemented yet.")
	else:
		mode = md

def network_steps(chunks, tasks):

	global doc
	global server_ip
	global shared_root

	net_tasks = []

	client = PhotoScan.NetworkClient()
	client.connect(server_ip)

	for task_params in tasks:
		new_task = PhotoScan.NetworkTask()
		for chunk in chunks:
			new_task.frames.append((chunk.key,0))
			new_task.name = task_params['name']
			for key in task_params:
				if key != 'name':
					new_task.params[key] = task_params[key]
		net_tasks.append(new_task)

	network_save = doc.path.replace(shared_root,'')
	batch_id = client.createBatch(network_save, net_tasks)
	client.resumeBatch(batch_id)

def load_images():

	global images_folder
	global process_folder
	global doc
	global save_file
	
	chunk_list = doc.chunks
	
	if any("Aligned Side A" in s for s in chunk_list) is False:
		chunk_aa = doc.addChunk()
		chunk_aa.label = "Aligned Side A"
	
	if any("Aligned Side B" in s for s in chunk_list) is False:
		chunk_ab = doc.addChunk()
		chunk_ab.label = "Aligned Side B"

	batch_chunks = [chunk_aa, chunk_ab]

	# This will create two chunks and load the images from SIDEA/SIDEB into each.
	path_druid = PhotoScan.app.getExistingDirectory("Specify DRUID path:")
	path_druid = path_druid.replace('\\','/')

	druid = path_druid.split('/')[-1]

	path_photos = path_druid + '/' + images_folder + '/'

	image_list_a = os.listdir(path_photos + '/SIDEA/')
	image_list_b = os.listdir(path_photos + '/SIDEB/')

	for n,i in enumerate(image_list_a):
		image_list_a[n] = path_photos + "/SIDEA/" + i

	for n,i in enumerate(image_list_b):
		image_list_b[n] = path_photos + "/SIDEB/" + i

	chunk_aa.addPhotos(image_list_a)
	chunk_ab.addPhotos(image_list_b)

	# Save file as .psx as it is requried for netwrok processing.
	save_path = path_druid + '/' + process_folder + '/'
	save_file = save_path + druid + '.psx'

	if not os.path.exists(save_path):
		os.makedirs(save_path)

	if not doc.save(save_file):
		PhotoScan.app.messageBox("Can’t save project")

	tasks = [{
	'name': 'MatchPhotos',
	'downscale': int(PhotoScan.HighAccuracy),
	'network_distribute': True,
	'keypoint_limit': '80000',
	'tiepoint_limit': '0'},
	{'name': 'AlignCameras',
	'network_distribute': True},
	{'name': 'DetectMarkers',
	'tolerance': '75',
	'network_distribute': True}]

	print(batch_chunks)
	network_steps(batch_chunks, tasks)

def add_scalebars():

	global doc

	accuracy = 0.00001

	pairings = ['49_50', '50_51', '52_53', '53_54', '55_56', '57_58', '58_59', '60_61', '61_62', '63_64']

	scale_values = {
	'49_50': 0.50024, '50_51': 0.50058,	'52_53': 0.25007, '53_54': 0.25034,
	'55_56': 0.25033, '57_58': 0.50027,	'58_59': 0.50053, '60_61': 0.25004,
	'61_62': 0.25033, '63_64': 0.25034 }

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

def setup_optimization():

	global doc

	for chunk in doc.chunks:

		if chunk.label == "Aligned Side A":
			chunk_oa = chunk.copy()
			chunk_oa.label = "Optimized Side A"
			chunk.enabled = False

		if chunk.label == "Aligned Side B":
			chunk_ob = chunk.copy()
			chunk_ob.label = "Optimized Side B"
			chunk.enabled = False

	add_scalebars()

def post_optimization():

	global doc

	chunks = []

	for chunk in doc.chunks:

		if chunk.label == "Optimized Side A":
			chunks.append(chunk)
		elif chunk.label == "Optimized Side B":
			chunks.append(chunk)

	tasks = [
	{'name': 'BuildDenseCloud',
	'downscale': int(PhotoScan.HighAccuracy),
	'network_distribute': True},
	{'name': 'BuildModel',
	'face_count': 3,
	'network_distribute': True},
	{'name': 'BuildTexture',
	'texture_count': 1,
	'texture_size': 4096,
	'network_distribute': True},
	{'name': 'ImportMasks',
	'method': 3,
	'network_distribute': True},
	{'name': 'AlignChunks',
	'match_filter_mask': 1,
	'match_point_limit': 80000,
	'network_distribute': True}]

	network_steps(chunks, tasks)

def merged_realign():

	global doc

	tasks = [{
	'name': 'MatchPhotos',
	'downscale': int(PhotoScan.HighAccuracy),
	'network_distribute': True,
	'filter_mask': '1',
	'keypoint_limit': '80000',
	'tiepoint_limit': '0'},
	{'name': 'AlignCameras',
	'network_distribute': True}]

	network_steps([doc.chunk], tasks)

def setup_merged_optimization():

	global doc

	for chunk in doc.chunks:

		if chunk.label == "Merged Chunk":
			chunk_om = chunk.copy()
			chunk_om.label = "Optimized Merged Chunk"
			#chunk_oa.accuracy_tiepoints = 0.1
			chunk.enabled = False

def create_final_model():
	global doc
	
	tasks = [
	{'name': 'BuildDenseCloud',
	'downscale': int(PhotoScan.HighAccuracy),
	'network_distribute': True},
	{'name': 'BuildModel',
	'face_count': 3,
	'network_distribute': True},
	{'name': 'BuildTexture',
	'texture_count': 1,
	'texture_size': 4096,
	'network_distribute': True}]

	network_steps([doc.chunk], tasks)

def optimize_first():
	global doc
	doc.chunk.optimizeCameras(True,True,False,False,True,True,False,False,False)

def optimize_all():
	global doc
	doc.chunk.optimizeCameras(True,True,True,True,True,True,True,True,True)

PhotoScan.app.addMenuItem("Automate/Import Images", load_images)
PhotoScan.app.addMenuItem("Automate/Setup Optimization", setup_optimization)
PhotoScan.app.addMenuItem("Automate/Post Optimization", post_optimization)
PhotoScan.app.addMenuItem("Automate/Realign with Masks", merged_realign)
PhotoScan.app.addMenuItem("Automate/Setup Merged Optimization", setup_merged_optimization)
PhotoScan.app.addMenuItem("Automate/Create Final Model", create_final_model)

PhotoScan.app.addMenuItem("Optimize/Partial", optimize_first)
PhotoScan.app.addMenuItem("Optimize/All", optimize_all)

PhotoScan.app.addMenuItem("Parts/Add Scale Bars", add_scalebars)
