import cv2
import numpy as np

from .utils import project_points


__all__ = ['triangulate_points', 
           'filter_triangulated_points',
           'filter_matching_inliers']


def triangulate_points(ptsLeft, ptsRight, projL, projR):

    """
    Uses Direct Linear Transform (DLT) method to triangulate 3D points from
    projections in the left and right image (usually inliers filtered from epipolar constraint)

    :param ptsLeft (np.array) : size(N,2) : inliers in the left image
    :param ptsRight (np.array) : size(N,2) : inlier in the right image
    :param projL (np.array) : size (3x4) left projection matrix such that x_L = PL * X_w
    :param projR (np.array) : size (3x4) right projection matrix such that x_R = PR * X_w
    """

    # triangulate points
    pts4D = cv2.triangulatePoints(projL, projR, ptsLeft.T, ptsRight.T)

    # convert from homogeneous coordinates to 3D
    pts3D = pts4D[:3,:]/((pts4D[-1,:]).reshape(1,-1))
    pts3D = pts3D.T

    # project reconstructed 3D points on to the images
    proj2D_left = project_points(pts3D, projL)
    proj2D_right = project_points(pts3D, projR)

    #calculate reprojection error
    reprojError = ((np.sqrt(((proj2D_left-ptsLeft)**2).sum(axis=1))) + (np.sqrt(((proj2D_right-ptsRight)**2).sum(axis=1))))/2

    return pts3D, reprojError

def filter_triangulated_points(points3D, reprojError, minDistThresh, maxRadius, repErrThresh):

    """
    Filters the triangulated values such that only values that lie within a certain distance on each cooridinate axis
    from the camera center and points which lie in front of the camera are considered 
    
    :param points3D (np.array) : size (Nx3) 3D world coordinates from DLT
    :param reprojError (np.array) : size (N) Reprojection error from triangulation.
    :param minDistThresh : Min distance threshold
    :param maxRadius     : Max radius from the camera pose.
    :param repErrThresh  : Reprojection error Threshold

    Returns:
        points3D_filter (np.array): size (Mx3): 3D world coordinates filtered
        mask_triangulation (np.array) : size (N) : contains boolean mask of filtered poitns
        ratioFilter (float): ratio of filtered points to triangulated points from DLT (M/Ns)
    """
    
    mask_x = np.logical_and((points3D[:, 0] > - 12), (points3D[:, 0] < 12))
    mask_y = np.logical_and((points3D[:, 1] < 2), (points3D[:, 1] > -8))
    mask_z = (points3D[:, 2] > minDistThresh)
    mask_R = (points3D[:, 0]**2 + points3D[:, 1]**2 + points3D[:, 2]**2) < maxRadius
    mask_reproj = reprojError < repErrThresh
    
    mask_triangulation = np.logical_and(np.logical_and(mask_x, mask_y, mask_z), mask_reproj)
    ratioFilter = sum(mask_triangulation)/len(mask_triangulation)
   
    points3D_filter = points3D[mask_triangulation]
    
    return points3D_filter, mask_triangulation, ratioFilter


def filter_matching_inliers(leftMatchesPoints, rightMatchedPoints, intrinsic, params):

    """
    :param leftMatchedPoints (np.array): size(N,2) matched feature points in left image
    :param rightMatchedPoints (np.array): size (N,2) matched feature points in right image
    :param instrinsic (np.array): size (3,3) : intrinsic camera calibration matrix
    :param params (AttriDict): contains parameters for the stereo configuration, 
                                detection and matching of features
    """

    args_debug = params.debug
    args_epipolar = params.geometry.epipolarGeometry

    for i in range(args_epipolar.numTrials):
        _, mask_epipolar = cv2.findEssentialMat(leftMatchesPoints,
                                                rightMatchedPoints,
                                                intrinsic,
                                                method = args_epipolar.method,
                                                prob = args_epipolar.probability,
                                                threshold = args_epipolar.threshold)
        
        mask_epipolar = mask_epipolar.ravel().astype(bool)
        ratio = sum(mask_epipolar) / len(mask_epipolar)
        
        if args_debug.logging.inliersFilterRANSAC:
            if (ratio > args_epipolar.inlierRatio):
                print("Iterations of 5-point algorithm: {}".format(i+1))
                print("Inlier Ratio :                   {}".format(ratio))
                print("Good Essential Matrix calculation is likely.")
                break
            else:
                print("Bad Essential Matrix likely")
                print("Inlier Ratio          : {}".format(ratio))
                print("Run again. Iters Left : {}".format(args_epipolar.numTrials-i))
                if i==args_epipolar.numTrials:
                    print("Fraction of inliers for E: {}".format(ratio))
                    print("Max iteration in 5-point algorithm trial reaches, bad E is likely ")

    left_inliers = leftMatchesPoints[mask_epipolar]
    right_inliers = rightMatchedPoints[mask_epipolar]

    return (left_inliers, right_inliers), mask_epipolar
