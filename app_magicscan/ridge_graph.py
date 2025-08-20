import glob
import os
from scipy.ndimage import gaussian_filter,  maximum_filter
import numpy as np

class Vertex:
    def __init__(self, id, dim):
        self.id = id
        self.dim = dim
        self.training = False
        self.polylines = set()
        self.coords = None

    # takes flat list of floats  x0, y0, x1, y1, ... , xn, yn
    def AddPoints(self, coordlist):
        flat_coords = np.array(coordlist)
        self.coords =  np.reshape(flat_coords, (-1, 2))
        #print(flat_coords)
        #print(self.coords)

class PolyLine:
    def __init__(self, id, dim):
        self.id = id
        self.dim = dim
        self.training = False
        self.vertices = set()
        self.rf_stats = None
        self.coords = None

    # takes flat list of floats  x0, y0, x1, y1, ... , xn, yn
    def AddPoints(self, coordlist):
        flat_coords = np.array(coordlist)
        self.coords =  np.reshape(flat_coords, (-1, 2))
        #print(flat_coords)
        #print(self.coords)

class LabeledRidgeGraph:
    def __init__(self):
        self.vertices = {}
        self.polylines = []
        self.labels = []

    def PolylineNeighbors(self, id):
        poly = self.polylines[id]
        if len(poly.vertices) != 2:
            print("whoa len of verts is:", len(poly.vertices))
            return [[],[]]
        return [list(self.vertices[id].polylines) for id in poly.vertices]
    def LoadGeom(self, name):
        with open(name, "r") as f:
            lines = f.readlines()
            for line in lines:
                tokens = line.split(" ")
                id = int(tokens[0])
                dim = int(tokens[1])
                if dim == 0:
                    points = [float(x) for x in tokens[2:]]
                    vert = Vertex(id, dim)
                    vert.AddPoints(points)
                    self.vertices[id] = vert
                if dim == 1:
                    points = [float(x) for x in tokens[2:]]
                    plyline = PolyLine(id, dim)
                    plyline.AddPoints(points)
                    self.polylines.append(plyline)
            print("num ply:", len(self.polylines), "num junct:", len(self.vertices))
        # HUGE ASSUMPTION that the "nodes" of the graph are polylines, and they come first
        # nodesname = name.replace("mlg_geom", "mlg_nodes")
        # with open(nodesname, "r") as f:
        #     lines = f.readlines()
        #     for line in lines:
        #         tokens = line.split(" ")
        #         id = int(tokens[0])

        print("reading edges...")
        edgesname = name.replace("mlg_geom", "mlg_edges")
        with open(edgesname, "r") as f:
            lines = f.readlines()
            for line in lines:
                tokens = line.split(" ")
                id = int(tokens[0])
                plys = [int(x) for x in tokens[1:] if int(x) != -1]

                for p in plys:
                    self.vertices[id].polylines.add(p)
                    self.polylines[p].vertices.add(id)

        print("built graph, num edges:", sum([len(v.polylines) for _,v in self.vertices.items()]))

    # def Count3Lengths(self):
    #     total = 0
    #     total_all_1 = 0
    #     total_all_2 = 0
    #     total_mix = 0
    #     for id in range(len(self.polylines)):
    #         prod = 1
    #         nelists = self.PolylineNeighbors(id)
    #         id_c = self.labels[id] == 1
    #         for id1 in nelists[0]:
    #             id1_c = self.labels[id1] == 1
    #             for id2 in nelists[1]:
    #                 id2_c = self.labels[id2] == 1
    #                 if id1 == id or id2 == id:
    #                     continue
    #                 kind = id_c + id1_c + id2_c
    #                 if kind == 3 :
    #                     total_all_1+= 1
    #                 elif kind == 0 :
    #                     total_all_2 += 1
    #                 else:
    #                     total_mix += 1
    #                 total += 1
    #     print("Num 3-lengths:", total)
    #     print("Num 3-all_fg:", total_all_1)
    #
    #     print("Num 3-all_bg:", total_all_2)
    #     print("Num 3-mix:", total_mix)
    #     print("--------------------")
    #     print("sanity:", total_all_1 + total_all_2 + total_mix)

    # 0 is nolabel, 1 is fg, 2 is bg
    def LoadLabels(self, name):
        with open(name, "r") as f:
            lines = f.readlines()[0:len(self.polylines)]
            self.labels = [int(x) for x in lines]
            print("read labels: ", len(self.labels))
    def find_latest_label_file(self, basefile):
        matching_files = glob.glob(basefile+".labels_*.txt")
        #print("picking latest form:", matching_files)
        if not matching_files:
            return None
        latest_file = max(matching_files, key=os.path.getmtime)
        return latest_file

def RasterizeRidgeGraph(shape, rg, foregroundclass=1, solid_width=2, smooth=1, outname=None):
    mask = np.zeros(shape).astype(np.float32) # make a background image
    for label, line in zip(rg.labels, rg.polylines):
        if label != foregroundclass:
            continue
        for p in line.coords:
            mask[int(p[1]), int(p[0])] = 1
    if solid_width > 0:
        mask = maximum_filter(mask, size=solid_width)
    if smooth > 0:
        mask = gaussian_filter(mask, sigma=smooth)

    mask=np.flipud(mask)
    if outname is not None:
        mask.astype(np.float32).tofile(outname)
    return mask


if __name__ == "__main__":
    print("debugging loader")
    # filename = fd.askopenfilename(title="Pick Geometry file", filetypes=[('text files', '*.txt')])
    # if filename is None:
    #     exit(1)
    filename = r"C:\Users\jediati\Desktop\JEDIATI\data\ARPA-H\test_images\visus-region6\visus-region6_inv_topo_3296x3834.raw.mlg_geom.txt"
    graph = LabeledRidgeGraph()
    graph.LoadGeom(filename)

    print("done loading geom")
