import matplotlib.pyplot as plt 
import pickle
def lossGraphPlotter(fileName,viewMode=False,saveMode=True):
    '''
    # fileName: full file path
    '''
    # loading the pickle file
    f=open(fileName,"rb")
    lossCollec=pickle.load(f)
    f.close()

    
    ep=[]
    vl=[]
    tl=[]
    ol=[]
    for ls in lossCollec:
        ep.append(ls["epoch"])
        # tl.append(ls["TrainLoss"]/1231)
        vl.append(ls["valLoss"])
        tl.append(ls["trainLoss"])
        ol.append(ls["ohemLoss"])


    # print(len(ep),len(vl))
    minVal=min(vl)
    minvl=[minVal]*len(ep)
    plt.clf()
    plt.rcParams["figure.figsize"] = (15,10)
    # for x in a:
    #     # plotting the points

    
    plt.plot(ep,vl,"g")
    plt.plot(ep,tl,"r")
    plt.plot(ep,ol,"orange")
    plt.plot(ep,minvl,"b",linestyle="dashed",marker="o",markevery=[ep[vl.index(min(vl))]-1])
    # i=0 
    # while(i < len(ep)):
    #     print(ep[i],vl[i])
    #     i+=1


    # naming the x axis 
    plt.xlabel('Epoch') 
    # naming the y axis 
        
    # giving a title to my graph 
    plt.ylabel("LOSS per image") 
    plt.title(fileName.strip(".pickle").split("/")[-3]+":  Loss(per image) Vs Epoch ") 
    plt.text(ep[len(ep)-1]*.65,max(vl[len(ep)-1],tl[len(ep)-1],ol[len(ep)-1])+(-max(vl[len(ep)-1],tl[len(ep)-1],ol[len(ep)-1])+max(vl[0],tl[0],ol[0]))*0.5,"Validation Loss per image (min={0:.2f} at epoch {1})".format(min(vl),ep[vl.index(min(vl))]),fontsize=12,color="green")
    plt.text(ep[len(ep)-1]*.65,max(vl[len(ep)-1],tl[len(ep)-1],ol[len(ep)-1])+(-max(vl[len(ep)-1],tl[len(ep)-1],ol[len(ep)-1])+max(vl[0],tl[0],ol[0]))*0.6,"Training Loss per image (min={0:.2f} at epoch {1})".format(min(tl),ep[tl.index(min(tl))]),fontsize=12,color="red")
    plt.text(ep[len(ep)-1]*.65,max(vl[len(ep)-1],tl[len(ep)-1],ol[len(ep)-1])+(-max(vl[len(ep)-1],tl[len(ep)-1],ol[len(ep)-1])+max(vl[0],tl[0],ol[0]))*0.7,"Ohem Loss per image (min={0:.2f} at epoch {1})".format(min(ol),ep[ol.index(min(ol))]),fontsize=12,color="orange")
    if(saveMode):
        plt.savefig(fileName.strip(".pickle")+"-graph.jpg")
    # plt.savefig( fileName.strip(".pickle")+"-Loss_per_image.jpg")
   
       
    
    # function to show the plot 
    if(viewMode):
        plt.show() 