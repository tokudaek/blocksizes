#!/usr/bin/env python
""" Compute the voronoi diagram provided the map and seeds
"""

import argparse
import logging
from logging import debug, info
import numpy as np
import pandas as pd
import scipy.spatial as spatial
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.path as path
import matplotlib as mpl
from matplotlib import patches
import smopy
import fiona
from shapely import geometry
from descartes import PolygonPatch
import copy
import scipy
from scipy.spatial import KDTree
import itertools
# import os
from os.path import join as pjoin
import igraph


##########################################################
def load_map(shppath):
    """Load shapefile map

    Args:
    shppath(str): path to the shapefile

    Returns:
    geometry.Polygon: hull polygon
    """

    shape = fiona.open(shppath)
    b = next(iter(shape))
    p = b['geometry']['coordinates'][0]
    x = [z[0] for z in p ]
    y = [z[1] for z in p ]
    poly = geometry.Polygon(p)
    return poly
    
##########################################################
def get_encbox_from_borders(poly):
    """Get enclosing box from borders

    Args:
    poly(shapely.geometry): arbitrary shape polygon

    Returns:
    int, int, int, int: xmin, ymin, xmax, ymax
    """
    return poly.bounds

##########################################################
def get_crossing_point_rectangle(v0, alpha, orient, encbox):
    mindist = 999999999

    for j, c in enumerate(encbox):
        i = j % 2
        d = (c - v0[i]) # xmin, ymin, xmax, ymax
        if alpha[i] == 0: d *= orient
        else: d = d / alpha[i] * orient
        if d < 0: continue
        if d < mindist: mindist = d

    p = v0 + orient * alpha * mindist
    return p

##########################################################
def get_boxed_polygons(vor, newvorvertices, newridgevertices, encbox):
    newvorregions = copy.deepcopy(vor.regions)
    # newvorregions = np.array([ np.array(f) for f in newvorregions])

    # Update voronoi regions to include added vertices and corners
    for regidx, rr in enumerate(vor.regions):
        reg = np.array(rr)
        if not np.any(reg == -1): continue
        foo = np.where(vor.point_region==regidx)
        seedidx = foo[0]

        newvorregions[regidx] = copy.deepcopy(rr)
        # Looking for ridges bounding my point
        for ridgeid, ridgepts in enumerate(vor.ridge_points):
            if not np.any(ridgepts == seedidx): continue
            ridgevs = vor.ridge_vertices[ridgeid]
            if -1 not in ridgevs: continue # I want unbounded ridges
            myidx = 0 if ridgevs[0] == -1 else 1

            newvorregions[regidx].append(newridgevertices[ridgeid][myidx])
        if -1 in newvorregions[regidx]:  newvorregions[regidx].remove(-1)

    tree = KDTree(vor.points)
    corners = itertools.product((encbox[0], encbox[2]), (encbox[1], encbox[3]))
    ids = []

    for c in corners:
        dist, idx = tree.query(c)
        k = len(newvorvertices)
        newvorvertices = np.row_stack((newvorvertices, c))
        newvorregions[vor.point_region[idx]].append(k)

    convexpolys = []
    for reg in newvorregions:
        if len(reg) == 0: continue
        points = newvorvertices[reg]
        hull = spatial.ConvexHull(points)
        pp = points[hull.vertices]
        convexpolys.append(pp)
    return convexpolys

##########################################################
def plot_finite_ridges(ax, vor):
    """Plot the finite ridges of voronoi

    Args:
    ax(matplotlib.Axis): axis to plot
    vor(spatial.Voronoi): instance generated by spatial.Voronoi
    """

    for simplex in vor.ridge_vertices:
        simplex = np.asarray(simplex)
        if np.any(simplex < 0): continue
        ax.plot(vor.vertices[simplex, 0], vor.vertices[simplex, 1], 'k-')

##########################################################
def create_bounded_ridges(vor, encbox, ax=None):
    """Create bounded voronoi vertices bounded by encbox

    Args:
    vor(spatial.Voronoi): voronoi structure
    encbox(float, float, float, float): xmin, ymin, xmax, ymax

    Returns:
    ret
    """

    center = vor.points.mean(axis=0)
    newvorvertices = copy.deepcopy(vor.vertices)
    newridgevertices = copy.deepcopy(vor.ridge_vertices)

    for j in range(len(vor.ridge_vertices)):
        pointidx = vor.ridge_points[j]
        simplex = vor.ridge_vertices[j]
        simplex = np.asarray(simplex)
        if np.any(simplex < 0):
            i = simplex[simplex >= 0][0] # finite end Voronoi vertex
            t = vor.points[pointidx[1]] - vor.points[pointidx[0]]  # tangent
            t = t / np.linalg.norm(t)
            n = np.array([-t[1], t[0]]) # normal
            # input(n)
            midpoint = vor.points[pointidx].mean(axis=0)
            orient = np.sign(np.dot(midpoint - center, n))
            far_point_clipped = get_crossing_point_rectangle(vor.vertices[i],
                                                             n,
                                                             orient,
                                                             encbox)
            ii = np.where(simplex < 0)[0][0] # finite end Voronoi vertex
            kk = newvorvertices.shape[0]
            newridgevertices[j][ii] = kk
            newvorvertices = np.row_stack((newvorvertices, far_point_clipped))
            if ax == None: continue
            ax.plot([vor.vertices[i,0], far_point_clipped[0]],
                     [vor.vertices[i,1], far_point_clipped[1]], 'k--')

            ax.plot(far_point_clipped[0], far_point_clipped[1], 'og')
    return newvorvertices, newridgevertices

def plot_bounded_ridges(ax, polys):
    for p in polys:
        pgon = plt.Polygon(p, color=np.random.rand(3,), alpha=0.5)
        ax.add_patch(pgon)
    ax.autoscale_view()
##########################################################
def plot_boxed_voronoi(ax, vor, b):
    ax.plot(vor.points[:, 0], vor.points[:, 1], 'o') # Plot seeds (points)
    ax.plot(vor.vertices[:, 0], vor.vertices[:, 1], 's') # Plot voronoi vertices

    plot_finite_ridges(ax, vor)

    newvorvertices, newridgevertices = create_bounded_ridges(vor, b)
    ax.add_patch(patches.Rectangle(b[0:2], b[2]-b[0], b[3]-b[1],
                                   linewidth=1, edgecolor='r', facecolor='none'))
    cells = get_boxed_polygons(vor, newvorvertices, newridgevertices, b)

    plot_bounded_ridges(ax, cells)
    return cells

##########################################################
def compute_cells_bounded_by_polygon(cells, mappoly):
    polys = []
    for c in cells:
        poly = geometry.Polygon(c)
        polygon1 = poly.intersection(mappoly)
        polys.append(polygon1)
    return polys

def plot_polygon(ax, pol, c):
    x,y = pol.exterior.xy
    z = list(zip(*pol.exterior.coords.xy))
    ax.add_patch(patches.Polygon(z, linewidth=2, edgecolor='r',
                                     facecolor=c))
def plot_bounded_cells(ax, polys):
    for pol in polys:
        if pol.geom_type == 'MultiPolygon':
            for polyg in pol.geoms:
                plot_polygon(ax, polyg, np.random.rand(3,))
        else:
            plot_polygon(ax, pol, np.random.rand(3,))

    ax.autoscale_view()

##########################################################
def random_sign(sampleshape):
    return (np.random.rand(*sampleshape) > .5).astype(int)*2 - 1

##########################################################
def create_graph_from_polys(polys):
    coords = set()

    for p in polys:
        x, y = p.exterior.coords.xy
        for xx, yy in zip(x, y):
            coords.add((xx, yy))

    coords = np.array(list(coords))
    # print(coords)
    # input()
    nvertices = len(coords)
    coordsidx = {}
    idx = 0
    for i, c in enumerate(coords):
        if c[0] not in coordsidx.keys(): coordsidx[c[0]] = {}
        coordsidx[c[0]][c[1]] = i
    edges = []
    weights = []

    for p in polys:
        x, y = p.exterior.coords.xy
        m = len(x)
        for i in range(m):
            s = coordsidx[x[i]][y[i]]
            j = (i+1)%m
            t = coordsidx[x[j]][y[j]]
            edges.append([s, t])
            p1 = np.array([x[i], y[i]])
            p2 = np.array([x[j], y[j]])
            weights.append(np.linalg.norm(p1 - p2))

    vattrs = dict(
        x = coords[:, 0],
        y = coords[:, 1],
    )

    eattrs = dict(
        weight = weights
    )
    g = igraph.Graph(nvertices, edges)
    g.simplify() # remove self-loops
    g.vs['x'] = coords[:, 0]
    g.vs['y'] = coords[:, 0]
    g.es['weight'] = weights
    igraph.plot(g, '/tmp/graph.pdf', layout=list(coords))
    return g

##########################################################
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--distrib', default='uniform', help='data distrib')
    parser.add_argument('--samplesz', default=50, type=int, help='sample size')
    parser.add_argument('--outdir', required=False, default='/tmp/', help='POIs in csv fmt')
    parser.add_argument('--seed', default=0, type=int)
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s] %(message)s',
    datefmt='%Y%m%d %H:%M', level=logging.INFO)

    figs, axs = plt.subplots(1, 3, figsize=(35, 15))

    # mappoly = load_map(args.shp)
    mappoly = geometry.Polygon([
        [0, 0],
        [0, 1],
        [1, 1],
        [1, 0],
    ])
    # bbox = get_encbox_from_borders(mappoly)
    bbox = [0, 0, 1, 1]
    # df = pd.read_csv(args.pois) # Load seeds

    dim = 2
    samplesz = args.samplesz

    if args.distrib == 'exponential':
        points = np.random.exponential(size=(samplesz, dim))
        points /= (np.max(points, 0)*2) # 0--0.5
        points *= random_sign((samplesz, 2))
        points += np.ones(dim)*.5
    elif args.distrib == 'linear':
        points = np.random.power(2, size=(samplesz, dim))
        points = 1 - points
        points /= 2 # 0--0.5
        points *= random_sign((samplesz, dim))
        points += np.ones(dim)*.5
    elif args.distrib == 'quadratic':
        points = np.random.power(3, size=(samplesz, dim))
        points = 1 - points # we want decreasing prob
        points /= 2 # 0--0.5
        points *= random_sign((samplesz, dim))
        points += np.ones(dim)*.5
    elif args.distrib == 'gaussian':
        points = np.random.normal([0, 0], scale=1, size=(samplesz, 2))
        points += np.abs(np.min(points, 0))
        points /= np.max(points, 0)
    elif args.distrib == 'uniform':
        points = np.random.rand(samplesz, 2)
    else:
        info('Please choose a distrib among ' \
             '[uniform, linear, quadratic, gaussian, exponential]')
        return
    vor = spatial.Voronoi(points) # Compute regular Voronoi

    spatial.voronoi_plot_2d(vor, ax=axs[0]) # Plot default unbounded voronoi

    cells = plot_boxed_voronoi(axs[1], vor, bbox)
    polys = compute_cells_bounded_by_polygon(cells, mappoly)
    g = create_graph_from_polys(polys)
    n = g.vcount()
    shortestpaths = np.array(g.shortest_paths(weights=g.es['weight']))
    avgpathlength = (np.sum(shortestpaths)) / (n* (n - 1))
    info('avgpathlength:{}'.format(avgpathlength))
    
    plot_bounded_cells(axs[2], polys)
    areas = [p.area for p in polys]
    centroids = np.array([np.array(p.centroid.coords)[0] for p in polys])
    orderedcentroids = centroids[vor.point_region-1] # Sort the region ids
    centroidsdists = scipy.spatial.distance.cdist(centroids, points).diagonal()
    #TODO: adjust above computation for the multiple polygons case
    areasmean = np.mean(areas)
    areasstd = np.std(areas)
    df = pd.DataFrame({'areasmean':areasmean, 'areasstd':areasstd,
                       'centroidsdists':centroidsdists})
    info('areas {:.3f} ({:.3f})'.format(areasmean, areasstd))
    df.to_csv(pjoin(args.outdir, 'voronoi.csv'), header=True, index=False)

    plt.savefig(pjoin(args.outdir, 'voronoi.pdf'))

if __name__ == "__main__":
    main()
