import cv2 as cv
import paho.mqtt.client as mqtt
import time

# mqtt parameters
local_mqtt_host = 'broker'
mqtt_port = 1883
mqtt_topic = 'faces'

# global variable indicating disconnect status
dc_flag = False

# create callback functions
def on_connect_local(local_client, userdata, flags, rc):
    """
    This function handles the callback from the broker when it sends acknowledgement of connection status.
    """

    if rc == 0:
        local_client.connected_flag = True
        print("Connected OK returned code = ", rc)
    else:
        print("Bad connection Returned code = ", rc)

def on_disconnect_local(local_client, userdata, rc):
    #global dc_flag
    print("Disconnected due to ", rc)
    #dc_flag = True

# initiate local client instance
local_client = mqtt.Client("detector")

# connection flag indicating connection status
local_client.connected_flag = False

# bind call back functions
local_client.on_connect = on_connect_local
local_client.on_disconnect = on_disconnect_local

# loop start
local_client.loop_start()

# make connection
local_client.connect(local_mqtt_host, mqtt_port, 60)

while not local_client.connected_flag:
    print("Waiting in loop")
    time.sleep(1)

# 1 should correspond to /dev/video1 , your USB camera.
# The 0 is reserved for the NX onboard camera or webcam on laptop
cap = cv.VideoCapture(0)
cap.set(3, 640)
cap.set(4, 480)

# initiate object tracker
tracker = cv.TrackerCSRT_create()

# read initial frame for customized bounding box
ret, frame = cap.read()
bbox = cv.selectROI('Tracking', frame, False)
initial_txt = 'Please draw a bounding box'
cv.putText(frame, initial_txt, (50, 50), cv.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv.LINE_AA)

# initialzie tracker using the bounding box
tracker.init(frame, bbox)

def drawBbox(frame, bbox):
    """
    A function that draws boudning box on a frame based on the bbox dimensions.
    """
    x, y, w, h = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
    cv.rectangle(frame, (x, y), ((x + w), (y+h)), (255, 0, 0), 2, 1)

# timestamps used for fps calculation
prev_frame_time = 0
new_frame_time = 0

# training samples stats and countdown
target_sample_num = 50
collected_num = 0
countdown = 5

i = 0
while True:

    # read frame
    ret, frame = cap.read()

    # get bbox and updates tracker
    ret, bbox = tracker.update(frame)

    # fps calculation
    new_frame_time = time.time()
    fps = 1.0/(new_frame_time - prev_frame_time)
    prev_frame_time = new_frame_time
    fps = int(fps)

    if ret:
        # draw bbox if traking succeeded
        drawBbox(frame, bbox)
    else:
        # print missing if not
        cv.putText(frame, 'lost', (100, 145), cv.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv.LINE_AA)

    # display status
    headline_txt = f'Capturing training samples...'
    fpd_txt = f'Camera feed @ ~{fps} fps'
    status_txt = f'Collection Status: {collected_num}/{target_sample_num}'

    cv.putText(frame, headline_txt, (30, 20), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv.LINE_AA)
    cv.putText(frame, fpd_txt, (30, 40), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv.LINE_AA)
    cv.putText(frame, status_txt, (30, 60), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv.LINE_AA)

    if i % 5 == 0 and collected_num < target_sample_num:
        ##### actual training samples with bounding box annotation #####
        ##### can be created here. object is cropped out here for demo #####

        # Extract object
        obj_extract = frame[y:y + h, x:x + w]

        # Encode extract to png
        rc, png = cv.imencode('.png', obj_extract)

        # convert png extract to bytes (for messaging)
        msg = png.tobytes()

        #if dc_flag:
        #local_client.connect(local_mqtt_host, mqtt_port, 60)
        local_client.publish(mqtt_topic, msg, qos=1, retain=False)

    if collected_num >= target_sample_num:
        exit_txt = f'Session ending in {countdown}'
        cv.putText(frame, exit_txt, (30, 80), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv.LINE_AA)
        if i % 10 == 0:
            countdown -= 1

    if countdown < 0:
        break

    i += 1

    cv.imshow('img', frame)
    if cv.waitKey(1) & 0xFF == ord('q'):
        break

# loop end
local_client.disconnect()

cap.release()
cv.destroyAllWindows()
