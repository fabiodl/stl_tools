from itertools import product
import struct

import numpy as np

import pylab
ASCII_FACET = """  facet normal  {face[0]:e}  {face[1]:e}  {face[2]:e}
    outer loop
      vertex    {face[3]:e}  {face[4]:e}  {face[5]:e}
      vertex    {face[6]:e}  {face[7]:e}  {face[8]:e}
      vertex    {face[9]:e}  {face[10]:e}  {face[11]:e}
    endloop
  endfacet"""

BINARY_HEADER = "80sI"
BINARY_FACET = "12fH"


def _build_binary_stl(facets):
    """returns a string of binary binary data for the stl file"""

    lines = [struct.pack(BINARY_HEADER, b'Binary STL Writer', len(facets)), ]
    for facet in facets:
        facet = list(facet)
        facet.append(0)  # need to pad the end with a unsigned short byte
        lines.append(struct.pack(BINARY_FACET, *facet))
    return lines


def _build_ascii_stl(facets):
    """returns a list of ascii lines for the stl file """

    lines = ['solid ffd_geom', ]
    for facet in facets:
        lines.append(ASCII_FACET.format(face=facet))
    lines.append('endsolid ffd_geom')
    return lines


def writeSTL(facets, file_name, ascii=False):
    """writes an ASCII or binary STL file"""

    f = open(file_name, 'wb')
    if ascii:
        lines = _build_ascii_stl(facets)
        lines_ = "\n".join(lines).encode("UTF-8")
        f.write(lines_)
    else:
        data = _build_binary_stl(facets)
        data = b"".join(data)
        f.write(data)

    f.close()


def roll2d(image, shifts):
    return np.roll(np.roll(image, shifts[0], axis=0), shifts[1], axis=1)


def numpy2stl(A, fn, scale=0.1, mask_val=-np.inf, ascii=False,
              calc_normals=False,
              max_width=235.,
              max_depth=140.,
              max_height=150.,
              solid=True):
    """
    Reads a numpy array, and outputs an STL file

    Inputs:
     A (ndarray) -  an 'm' by 'n' 2D numpy array
     fn (string) -  filename to use for STL file

    Optional input:
     scale (float)  -  scales the height (surface) of the
                       resulting STL mesh. Tune to match needs

     mask_val (float) - any element of the inputted array that is less
                        than this value will not be included in the mesh.
                        default renders all vertices (x > -inf for all float x)

     ascii (bool)  -  sets the STL format to ascii or binary (default)

     calc_normals (bool) - sets whether surface normals are calculated or not

     max_width, max_depth, max_height (floats) - maximum size of the stl
                                                object (in mm). Match this to
                                                the dimensions of a 3D printer
                                                platform

    Returns: (None)
    """
    m, n = A.shape
    if n >= m:
        A = np.rot90(A, k=3)
        m, n = n, m
    A = scale * (A - A.min())

    facets = []
    mask = np.zeros((m, n))
    for i, k in product(range(m - 1), range(n - 1)):

        this_pt = np.array([i - m / 2., k - n / 2., A[i, k]])
        top_right = np.array([i - m / 2., k + 1 - n / 2., A[i, k + 1]])
        bottom_left = np.array([i + 1. - m / 2., k - n / 2., A[i + 1, k]])
        bottom_right = np.array(
            [i + 1. - m / 2., k + 1 - n / 2., A[i + 1, k + 1]])

        if calc_normals:
            n1 = np.cross(this_pt - top_right, bottom_left - top_right)
            n1 = n1 / np.linalg.norm(n1)

            n2 = np.cross(bottom_right - top_right, bottom_left - top_right)
            n2 = n2 / np.linalg.norm(n2)
        else:
            n1, n2 = np.zeros(3), np.zeros(3)

        if (this_pt[-1] > mask_val and top_right[-1] > mask_val and
                bottom_left[-1] > mask_val):

            facet = np.concatenate([n1, top_right, this_pt, bottom_right])
            mask[i, k] = 1
            mask[i, k + 1] = 1
            mask[i + 1, k] = 1
            facets.append(facet)

        if (this_pt[-1] > mask_val and bottom_right[-1] > mask_val and
                bottom_left[-1] > mask_val):

            facet = np.concatenate([n2, bottom_right, this_pt, bottom_left])
            facets.append(facet)
            mask[i, k] = 1
            mask[i + 1, k + 1] = 1
            mask[i + 1, k] = 1
    facets = np.array(facets)

    if solid:
        edge_mask = np.sum([roll2d(mask, (i, k))
                           for i, k in product([-1, 0, 1], repeat=2)], axis=0)
        edge_mask[np.where(edge_mask == 9.)] = 0.
        edge_mask[np.where(edge_mask != 0.)] = 1.
        edge_mask[0::m - 1,:] = 1.
        edge_mask[:, 0::n - 1] = 1.
        X, Y = np.where(edge_mask == 1.)
        locs = zip(X - m / 2., Y - n / 2.)
        minval = facets[:, 5::3].min() - 0.1 * facets[:, 5::3].ptp()
        #[0, 0, 0, 1, 1, z, 1, 1, z, 1, 1, z]
        bottom = []
        for i, facet in enumerate(facets):
            if (facet[3], facet[4]) in locs:
                facets[i][5] = minval
            if (facet[6], facet[7]) in locs:
                facets[i][8] = minval
            if (facet[9], facet[10]) in locs:
                facets[i][11] = minval
            this_bottom = np.concatenate(
                [facet[:3], facet[6:8], [minval], facet[3:5], [minval], facet[9:11], [minval]])
            bottom.append(this_bottom)

        facets = np.concatenate([facets, bottom])

    xsize = facets[:, 3::3].ptp()
    if xsize > max_width:
        facets = facets * float(max_width) / xsize

    ysize = facets[:, 4::3].ptp()
    if ysize > max_depth:
        facets = facets * float(max_depth) / ysize

    zsize = facets[:, 5::3].ptp()
    if zsize > max_height:
        facets = facets * float(max_height) / zsize

    writeSTL(facets, fn, ascii=ascii)


if __name__ == "__main__":
    from scipy.ndimage import gaussian_filter
    A = 256 * pylab.imread("openmdao.png")
    A =  A[:,:, 0] + 1.*A[:,:, 3] # Compose some elements from RGBA to give depth
    A = gaussian_filter(A, 2)  # smoothing
    numpy2stl(A, "OpenMDAO-logo.stl", scale=0.05, mask_val=1.)
