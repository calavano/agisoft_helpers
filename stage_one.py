import PhotoScan
import os

doc = PhotoScan.app.document

# Setup a few variables.
server_ip = ''
shared_root = ''
images_folder = 'JPG'
process_folder = 'PROCESSING'
# TODO: Add support for non-network processing.
mode = 'network'

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

# Setup chunks for top and bottom sides.
chunk_aa = doc.addChunk()
chunk_ab = doc.addChunk()
chunk_aa.label = "Aligned Side A"
chunk_ab.label = "Aligned Side B"

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

network_steps(batch_chunks, tasks)