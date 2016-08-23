import PhotoScan

server_ip = ''

doc = PhotoScan.app.document

for chunk in doc.chunks:

	if chunk.label = "Optimized Side A":
		chunk_oa = chunk
	elif chunk.label = "Optimized Side B":
		chunk_ob = chunk

client = PhotoScan.NetworkClient()
client.connect(server_ip)

task1 = PhotoScan.NetworkTask()
for c in [chunk_oa,chunk_ob]:
	task1.frames.append((c.key,0))
task1.name = 'BuildDenseCloud'
task1.params['downscale'] = int(PhotoScan.HighAccuracy)
task1.params['network_distribute'] = True

task2 = PhotoScan.NetworkTask()
for c in [chunk_oa,chunk_ob]:
    task2.chunks.append(c.key)
task2.name = 'BuildModel'
task2.params['face_count'] = 3
task2.params['network_distribute'] = True

task3 = PhotoScan.NetworkTask()
for c in [chunk_oa,chunk_ob]:
    task3.chunks.append(c.key)
task3.name = 'BuildTexture'
task3.params['texture_count'] = 1
task3.params['texture_size'] = 4096
task3.params['network_distribute'] = True

task4 = PhotoScan.NetworkTask()
for c in [chunk_oa,chunk_ob]:
    task3.chunks.append(c.key)
task4.name = 'ImportMasks'
task4.params['method'] = 3
task4.params['network_distribute'] = True

task5 = PhotoScan.NetworkTask()
for c in [chunk_oa,chunk_ob]:
    task3.chunks.append(c.key)
task5.name = 'AlignChunks'
task5.params['match_filter_mask'] = 1
task5.params['match_point_limit'] = 80000
task5.params['network_distribute'] = True

network_save = save_file.replace(shared_root,'')
batch_id = client.createBatch(network_save, [task1, task2])
client.resumeBatch(batch_id)
