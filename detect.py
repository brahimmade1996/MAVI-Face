from __future__ import print_function
import os
import argparse
import torch
import torch.backends.cudnn as cudnn
import numpy as np
from data import cfg_mnet, cfg_re50
from layers.functions.prior_box import PriorBox
from utils.nms.py_cpu_nms import py_cpu_nms
import cv2
from models.retinaface import RetinaFace
from utils.box_utils import decode, decode_landm
import time
import numpy as np
import os
import cv2
import numpy as np
import os
from os.path import isfile, join
import time
import sys
from os.path import isfile, join
from toolbox.makedir import make

parser = argparse.ArgumentParser(description='Retinaface')

parser.add_argument('-m', '--trained_model', default='Resnet50_epoch_28_noGrad_FT_Adam_lre3',
                    type=str, help='Trained state_dict file path to open')
parser.add_argument('--network', default='resnet50', help='Backbone network mobile0.25 or resnet50')
parser.add_argument('--cpu', action="store_true", default=False, help='Use cpu inference')
parser.add_argument('--confidence_threshold', default=0.055, type=float, help='confidence_threshold')
parser.add_argument('--top_k', default=5000, type=int, help='top_k')
parser.add_argument('--nms_threshold', default=0.4, type=float, help='nms_threshold')
parser.add_argument('--keep_top_k', default=750, type=int, help='keep_top_k')
parser.add_argument('-s', '--save_image', action="store_true", default=True, help='show detection results')
parser.add_argument('--vis_thres', default=0.055, type=float, help='visualization_threshold')
parser.add_argument('--area_thres', default=225, type=float, help='visualization_threshold')
parser.add_argument('--mode', default="images", type=str, help='images: for image inference, video: for video inference')
parser.add_argument('--save_name', default="test", type=str, help='folder in which you inference will be saved in inference/outputs/<save_name>')
args = parser.parse_args()


def check_keys(model, pretrained_state_dict):
    ckpt_keys = set(pretrained_state_dict.keys())
    model_keys = set(model.state_dict().keys())
    used_pretrained_keys = model_keys & ckpt_keys
    unused_pretrained_keys = ckpt_keys - model_keys
    missing_keys = model_keys - ckpt_keys
    print('Missing keys:{}'.format(len(missing_keys)))
    print('Unused checkpoint keys:{}'.format(len(unused_pretrained_keys)))
    print('Used keys:{}'.format(len(used_pretrained_keys)))
    assert len(used_pretrained_keys) > 0, 'load NONE from pretrained checkpoint'
    return True


def remove_prefix(state_dict, prefix):
    ''' Old style model is stored with all names of parameters sharing common prefix 'module.' '''
    print('remove prefix \'{}\''.format(prefix))
    f = lambda x: x.split(prefix, 1)[-1] if x.startswith(prefix) else x
    return {f(key): value for key, value in state_dict.items()}


def load_model(model, pretrained_path, load_to_cpu):
    print('Loading pretrained model from {}'.format(pretrained_path))
    if load_to_cpu:
        pretrained_dict = torch.load(pretrained_path, map_location=lambda storage, loc: storage)
    else:
        device = torch.cuda.current_device()
        pretrained_dict = torch.load(pretrained_path, map_location=lambda storage, loc: storage.cuda(device))
    if "state_dict" in pretrained_dict.keys():
        pretrained_dict = remove_prefix(pretrained_dict['state_dict'], 'module.')
    else:
        pretrained_dict = remove_prefix(pretrained_dict, 'module.')
    check_keys(model, pretrained_dict)
    model.load_state_dict(pretrained_dict, strict=False)
    return model


def infer(net,img_raw):
    # print(sys.getsizeof(img_raw))
    img = np.float32(img_raw)

    im_height, im_width, _ = img.shape
    scale = torch.Tensor([img.shape[1], img.shape[0], img.shape[1], img.shape[0]])
    img -= (104, 117, 123)
    img = img.transpose(2, 0, 1)
    img = torch.from_numpy(img).unsqueeze(0)
    img = img.to(device)
    scale = scale.to(device)

    loc, conf, landms = net(img)  # forward pass

    priorbox = PriorBox(cfg, image_size=(im_height, im_width))
    priors = priorbox.forward()
    priors = priors.to(device)
    prior_data = priors.data
    boxes = decode(loc.data.squeeze(0), prior_data, cfg['variance'])
    boxes = boxes * scale / resize
    boxes = boxes.cpu().numpy()
    scores = conf.squeeze(0).data.cpu().numpy()[:, 1]
    landms = decode_landm(landms.data.squeeze(0), prior_data, cfg['variance'])
    scale1 = torch.Tensor([img.shape[3], img.shape[2], img.shape[3], img.shape[2],
                            img.shape[3], img.shape[2], img.shape[3], img.shape[2],
                            img.shape[3], img.shape[2]])
    scale1 = scale1.to(device)
    landms = landms * scale1 / resize
    landms = landms.cpu().numpy()

    # ignore low scores
    inds = np.where(scores > args.confidence_threshold)[0]
    boxes = boxes[inds]
    landms = landms[inds]
    scores = scores[inds]

    # keep top-K before NMS
    order = scores.argsort()[::-1][:args.top_k]
    boxes = boxes[order]
    landms = landms[order]
    scores = scores[order]

    # do NMS
    dets = np.hstack((boxes, scores[:, np.newaxis])).astype(np.float32, copy=False)
    keep = py_cpu_nms(dets, args.nms_threshold)
    # keep = nms(dets, args.nms_threshold,force_cpu=args.cpu)
    dets = dets[keep, :]
    landms = landms[keep]

    # keep top-K faster NMS
    dets = dets[:args.keep_top_k, :]
    landms = landms[:args.keep_top_k, :]

    dets = np.concatenate((dets, landms), axis=1)

    #removing small face predictions
    area_thresh=args.area_thres
    dets=dets[np.where(np.multiply(dets[:,2],dets[:,3])>=area_thresh)[0]]
    # show image
    
    for b in dets:
        if b[4] < args.vis_thres:
            continue
        text = "{:.4f}".format(b[4])
        b = list(map(int, b))
        cv2.rectangle(img_raw, (b[0], b[1]), (b[2], b[3]), (0, 0, 255), 2)
        cx = b[0]
        cy = b[1] + 12
        cv2.putText(img_raw, text, (cx, cy),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255))

        # landms
        cv2.circle(img_raw, (b[5], b[6]), 1, (0, 0, 255), 4)
        cv2.circle(img_raw, (b[7], b[8]), 1, (0, 255, 255), 4)
        cv2.circle(img_raw, (b[9], b[10]), 1, (255, 0, 255), 4)
        cv2.circle(img_raw, (b[11], b[12]), 1, (0, 255, 0), 4)
        cv2.circle(img_raw, (b[13], b[14]), 1, (255, 0, 0), 4)
    
    return img_raw


if __name__ == '__main__':
    torch.set_grad_enabled(False)
    cfg = None
    if args.network == "mobile0.25":
        cfg = cfg_mnet
    elif args.network == "resnet50":
        cfg = cfg_re50
    # net and model
    net = RetinaFace(cfg=cfg, phase = 'test')
    modelPath=join(os.getcwd(),"weights",(args.trained_model+".pth"))
    net = load_model(net, modelPath, args.cpu)
    net.eval()
    print('Finished loading model!')
    print(net)
    cudnn.benchmark = True
    device = torch.device("cpu" if args.cpu else "cuda")
    net = net.to(device)

    resize = 1
    saveName=args.save_name
    #now loading images
    if(args.mode=="images"):
        pathIn=join(os.getcwd(),"inference","inputImages")
        files = [f for f in os.listdir(pathIn) if isfile(join(pathIn, f))]
        print("inferning on {} image files".format(len(files)))
        files.sort()
        beginTime=time.time()
        for i,file in enumerate(files):
            print(file)
            img_raw = cv2.imread(join(pathIn,file), cv2.IMREAD_COLOR)
            updatedImg=infer(net,img_raw)
            if(i%100==0):
                print("Time taken for 100 image inference and savings= {} sec".format(time.time()-beginTime))
                beginTime=time.time()
            saveFolder=join(os.getcwd(),"inference","output",args.save_name)
            make(saveFolder)
            cv2.imwrite(join(saveFolder,file), img_raw)

    elif(args.mode=="videos"):
        pathIn=join(os.getcwd(),"inference","inputVideos")
        files = [f for f in os.listdir(pathIn) if isfile(join(pathIn, f))]
        print("inferning on {} video files".format(len(files)))
        for i,video in enumerate(files):
            print(video)

            # reading from my video
            realvideo=cv2.VideoCapture(join(pathIn,video))
            
            #setting up for new video
            saveFolder=join(os.getcwd(),"inference","output",args.save_name,"video")
            make(saveFolder)

            pathOut=join(saveFolder,"output-{}.avi".format(video.split(".")[0]))
            print(pathOut)
            # frame size (width,height)
            size=(int(realvideo.get(cv2.CAP_PROP_FRAME_WIDTH)),int(realvideo.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            fps=int(realvideo.get(cv2.CAP_PROP_FPS))
            out=cv2.VideoWriter(pathOut,cv2.VideoWriter_fourcc(*'DIVX'),fps,size)
            print("Total frames= {}".format(realvideo.get(cv2.CAP_PROP_FRAME_COUNT)))
            counter=0
            while(True):
                print(counter)
                counter+=1
                ret,img_raw=realvideo.read()
                if(ret):
                    out.write(infer(net,img_raw))
                else:
                    break
            
            out.release()
            

    



