import PhotoScan
import os
import re

# Specify folder of unique identifier.
# Files must be in the following locations:
# [identifier]
#   \JPG\
#       \SIDEA\ -- location of jpegs for top view
#       \SIDEB\ -- location of jpegs for bottom view
#   \PROCESSING\ -- location to be used for psx file
#   \EXPORT\
#       \OBJ\
#       \PLY\

# Note that a lot of these tasks only work when chunks have specific
# labels. Many of the tasks will only work when performed at the
# appropriate times.

doc = PhotoScan.app.document
server_ip = '127.0.0.1'
shared_root = 'Z:/'
images_folder = 'JPG'
process_folder = 'PROCESSING'
export_folder = 'EXPORT'
mode = 'network'

#
# Handles starting a network batch jobs.
# Accepts an array of hashes of tasks/parameters.
#
def start_network_batch_process(chunks, tasks):
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

	network_save = PhotoScan.app.document.path.replace(shared_root,'')
	batch_id = client.createBatch(network_save, net_tasks)
	client.resumeBatch(batch_id)

#
# Loads images from two 'sides', aligns cameras, and detects markers.
# 
def load_images():
	global images_folder
	global process_folder
	global doc
	global save_file
	
	chunk_list = PhotoScan.app.document.chunks
	
	if any("Aligned Side A" in s for s in chunk_list) is False:
		chunk_aa = PhotoScan.app.document.addChunk()
		chunk_aa.label = "Aligned Side A"
	
	if any("Aligned Side B" in s for s in chunk_list) is False:
		chunk_ab = PhotoScan.app.document.addChunk()
		chunk_ab.label = "Aligned Side B"

	batch_chunks = [chunk_aa, chunk_ab]

	# This will create two chunks and load the images from SIDEA/SIDEB into each.
	path_druid = PhotoScan.app.getExistingDirectory("Specify DRUID path:")
	path_druid = path_druid.replace('\\','/')

	druid = path_druid.split('/')[-1]

	path_photos = path_druid + '/' + images_folder + '/'

	# TODO: create a loop for a N+X number of 'sides'.
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

	if not PhotoScan.app.document.save(save_file):
		PhotoScan.app.messageBox("Can’t save project")

	tasks = [{
	'name': 'MatchPhotos',
	'downscale': int(PhotoScan.HighestAccuracy),
	'network_distribute': True,
	'keypoint_limit': '80000',
	'tiepoint_limit': '0'},
	{'name': 'AlignCameras',
	'network_distribute': True},
	{'name': 'DetectMarkers',
	'tolerance': '75',
	'network_distribute': True}]

	start_network_batch_process(batch_chunks, tasks)

#
# Add scale bars. 
# Uses encoded markers and known values in meters.
#
def add_scalebars():
	global doc

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

#
# Creates duplicates of the 'alignment chunks'.
# This allows you to mess up the optimization of the 'alignment chunks'
# without worrying about needing to perform a new alignment.
#
def setup_optimize():

	for chunk in PhotoScan.app.document.chunks:

		if chunk.label == "Aligned Side A":
			chunk_oa = chunk.copy()
			chunk_oa.label = "Optimized Side A"
			chunk.enabled = False

		if chunk.label == "Aligned Side B":
			chunk_ob = chunk.copy()
			chunk_ob.label = "Optimized Side B"
			chunk.enabled = False

#
# Optimizes the object using the CHI-method.
# In it's current form, this is blindly performed. There are situations where this will
# remove too many points. This doesn't seem to be good  for images using on a turntable.
def perform_chi_optimize():
	gradual_selection_reconstructionuncertainty_ten()
	delete_and_optimize()
	gradual_selection_reconstructionuncertainty_ten()
	delete_and_optimize()

	var = gradual_selection_reprojectionerror()

	while var >= 1:
		var = gradual_selection_reprojectionerror()
		delete_and_optimize()

	if var <= 1.0:
		PhotoScan.app.document.chunk.tiepoint_accuracy = 0.1
	
	while var >= 0.3:
		var = gradual_selection_reprojectionerror()
		delete_and_optimize_all()

#
# Standard optimization routine.
# Duplicates initial chunks, adds scale bars, blindly performs the
# Chi-method of optimization.
#
def optimize_chi():
	setup_optimize()
	add_scalebars()
	perform_chi_optimize()

#
# Builds dense cloud, model, texture, creates maks, aligns chunks.
#
def post_optimize_two_side():
	chunks = []

	for chunk in PhotoScan.app.document.chunks:

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

	start_network_batch_process(chunks, tasks)

#
# Merge chunks and align masked photos.
#
def merged_and_align():

	tasks = [{
	'name': 'MatchPhotos',
	'downscale': int(PhotoScan.HigesthAccuracy),
	'network_distribute': True,
	'filter_mask': '1',
	'keypoint_limit': '80000',
	'tiepoint_limit': '0'},
	{'name': 'AlignCameras',
	'network_distribute': True}]

	start_network_batch_process([PhotoScan.app.document.chunk], tasks)
#
#
#
def optimize_merged_sides():
	setup_merged_optimization()

#
# Creates duplicate of the 'merged alignment chunk'.
# This allows you to mess up the optimization of the merged chunk
# without worrying about needing to perform a new alignment.
#
def setup_merged_optimization():
	for chunk in PhotoScan.app.document.chunks:
		if chunk.label == "Merged Chunk":
			chunk_om = chunk.copy()
			chunk_om.label = "Optimized Merged Chunk"
			#chunk_oa.accuracy_tiepoints = 0.1
			chunk.enabled = False

#
# Creates final model and textures
#
def create_dense_and_model():
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

	start_network_batch_process([PhotoScan.app.document.chunk], tasks)

#
# Deletes selected points and optimizes with some options.
#
def delete_and_optimize():
	delete_selected_points()
	optimize_partial()

#
# Deletes selected points and optimizes with all options.
#
def delete_and_optimize_all():
	delete_selected_points()
	optimize_all()

#
# Performs a gradual selection using 'reprojection error'
# Blindly selects 10% of the points.
# 
def gradual_selection_reprojectionerror():
	global doc

	f = PhotoScan.PointCloud.Filter()
	f.init(PhotoScan.app.document.chunk, PhotoScan.PointCloud.Filter.ReprojectionError)

	target_percent = 10
	points = PhotoScan.app.document.chunk.point_cloud.points.__len__()
	target = int(points / target_percent)
	thresh = 1
	thresh_jump = 1
	selected = points

	high = False
	low  = False

	while selected != target:
		selected = 0
		f.selectPoints(thresh)
		for point in PhotoScan.app.document.chunk.point_cloud.points:
			if point.selected:
				selected += 1
		if selected == target:
			break
		elif selected > target:
			high = True
			thresh += thresh_jump
		else:
			low = True
			thresh -= thresh_jump
		if high & low:
			high = False
			low = False
			thresh_jump = thresh_jump / 10

	return thresh
#
# Performs a gradual selection using 'reconstruction uncertainty'
# Uses the hard-coded value of '10'
# 
def gradual_selection_reconstructionuncertainty_ten():
	global doc

	f = PhotoScan.PointCloud.Filter()
	f.init(PhotoScan.app.document.chunk, PhotoScan.PointCloud.Filter.ReconstructionUncertainty)
	f.selectPoints(10)

#
# Performs a gradual selection using 'reconstruction uncertainty'
# Blindly selects 10% of the points.
# 
def gradual_selection_reconstructionuncertainty():
	global doc

	f = PhotoScan.PointCloud.Filter()
	f.init(PhotoScan.app.document.chunk, PhotoScan.PointCloud.Filter.ReconstructionUncertainty)

	target_percent = 10
	points = PhotoScan.app.document.chunk.point_cloud.points.__len__()
	target = int(points / target_percent)
	thresh = 100
	thresh_jump = 100
	selected = points

	high = False
	low  = False

	while selected != target:
		selected = 0
		f.selectPoints(thresh)
		for point in PhotoScan.app.document.chunk.point_cloud.points:
			if point.selected:
				selected += 1
		if selected == target:
			break
		elif selected > target:
			high = True
			thresh += thresh_jump
		else:
			low = True
			thresh -= thresh_jump
		if high & low:
			high = False
			low = False
			thresh_jump = thresh_jump / 10
#
# Deletes selected points
#
def delete_selected_points():
	PhotoScan.app.document.chunk.point_cloud.removeSelectedPoints()

#
# Exports a PLY and OBJ
#
def export_models():
	global export_folder

	path = re.sub(r"PROCESSING/.*",'',PhotoScan.app.document.path)
	export = path + export_folder
	ply = export + '/PLY/test.ply'
	obj = export + '/OBJ/test.obj'

	# export obj
	PhotoScan.app.document.chunk.exportModel(obj, False, 6, PhotoScan.ImageFormatPNG, True, False, False, False, False, False, False, '', PhotoScan.ModelFormatOBJ)

	# export ply
	PhotoScan.app.document.chunk.exportModel(ply, False, 6, PhotoScan.ImageFormatPNG, True, False, False, False, False, False, False, '', PhotoScan.ModelFormatPLY)

# optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, fit_b1=True?, fit_b2=True?, fit_k1=True,
#                 fit_k2=True, fit_k3=True, fit_k4=False, fit_p1=True, fit_p2=True, fit_p3=False,
#                 fit_p4=False, fit_shutter=False[, progress])

#
# Optimizes some of the options
# Selections according to the CHI-method
# 
def optimize_partial():
	global doc
	PhotoScan.app.document.chunk.optimizeCameras(True,True,True,True,True,True,True,True,False,True,True,False,False,False)

#
# Optimizes all of the options.
#
def optimize_all():
	global doc
	PhotoScan.app.document.chunk.optimizeCameras(True,True,True,True,True,True,True,True,True,True,True,True,True,False)

#
# Deletes all chunks other than Algined Side A and B.
# Assumes you did not the 'aligned' sides.
# WARNING: This immediately deletes all other chunks.
def revert_to_clean():
	for chunk in PhotoScan.app.document.chunks:
		if chunk.label != 'Aligned Side A' and chunk.label != 'Aligned Side B':
			PhotoScan.app.document.remove(chunk)
		else:
			chunk.enabled = True
#
# Moves viewport to face the center of the ROI box.
# This doesn't seem to always work.
#
def reset_view():
	PhotoScan.app.viewpoint.coo = PhotoScan.app.document.chunk.region.center
	PhotoScan.app.viewpoint.rot = PhotoScan.app.document.chunk.region.rot
	PhotoScan.app.viewpoint.mag = 100

#
# Attempts to create the region ROI. This places the center of the ROI region
# at the midpoint of all of the scale bar markers.
#
def create_roi():
	x, y, z = 0, 0, 0
	
	for chunk in PhotoScan.app.document.chunks:
		if chunk.label == 'Aligned Side A':
			x, y, z = 0, 0, 0
			num_markers = chunk.markers.__len__()
			for marker in chunk.markers:
				position = marker.position
				x += marker.position.x
				y += marker.position.y
				z += marker.position.z
			
			cent_x = x / num_markers
			cent_y = y / num_markers
			cent_z = z / num_markers

			newregion = PhotoScan.Region()
			newregion.size = chunk.region.size
			newregion.rot = chunk.region.rot
			newregion.center = PhotoScan.Vector([cent_x, cent_y, cent_z])
			chunk.region = newregion

			#
			# marker = PhotoScan.app.document.chunk.markers[0]
			# vector = marker.position
			# x = marker.position.x
			# x y z
			# Vector([0.7479940243319407, -1.4430349960110231, -5.8724660659394265])
			# Vector([-1.6652483720013491, -0.3325686787498139, -7.089723067502055])
			# Vector([-0.028839785332500246, 1.5206106060029403, -8.642452896180526])
			# Vector([2.3800205218926234, 0.4360515674969152, -7.401010090930162])
			# Size = Vector([4.026988702016849, 0.5133328430585171, 1.2496546164023838])

#
# Setup Menus
#
PhotoScan.app.addMenuItem("Automate/Flipflop/1. Import Images", load_images)
PhotoScan.app.addMenuItem("Automate/Flipflop/2. CHI Optimize", optimize_chi)
PhotoScan.app.addMenuItem("Automate/Flipflop/3. Model, Mask, Align", post_optimize_two_side)
PhotoScan.app.addMenuItem("Automate/Flipflop/4. Merge and Align Sides", merged_and_align)
PhotoScan.app.addMenuItem("Automate/Flipflop/5. Optimize Merged", merged_and_align)
PhotoScan.app.addMenuItem("Automate/Flipflop/6. Create Dense, Model, and Texture", create_dense_and_model)
PhotoScan.app.addMenuItem("Automate/Flipflop/7. Export Models", export_models)

PhotoScan.app.addMenuItem("Reset/Back to Align", revert_to_clean)
PhotoScan.app.addMenuItem("Reset/Reset View", reset_view)

PhotoScan.app.addMenuItem("Optimize/Cameras/Partial", optimize_partial)
PhotoScan.app.addMenuItem("Optimize/Cameras/All", optimize_all)
PhotoScan.app.addMenuItem("Optimize/Selection/Reconstruction Uncertainty 10", gradual_selection_reconstructionuncertainty_ten)
PhotoScan.app.addMenuItem("Optimize/Selection/Reconstruction Uncertainty 10%", gradual_selection_reconstructionuncertainty)
PhotoScan.app.addMenuItem("Optimize/Selection/Reprojection Error", gradual_selection_reprojectionerror)

PhotoScan.app.addMenuItem("Parts/Add Scale Bars", add_scalebars)

