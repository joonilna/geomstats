"""The manifold of symmetric positive definite (SPD) matrices."""

import math

import geomstats.backend as gs
import geomstats.vectorization
from geomstats.geometry.base import OpenSet
from geomstats.geometry.general_linear import GeneralLinear
from geomstats.geometry.matrices import Matrices
from geomstats.geometry.riemannian_metric import RiemannianMetric
from geomstats.geometry.symmetric_matrices import SymmetricMatrices


class SPDMatrices(OpenSet):
    """Class for the manifold of symmetric positive definite (SPD) matrices.

    Parameters
    ----------
    n : int
        Integer representing the shape of the matrices: n x n.
    """

    def __init__(self, n, **kwargs):
        super(SPDMatrices, self).__init__(
            dim=int(n * (n + 1) / 2),
            metric=SPDMetricAffine(n),
            ambient_space=SymmetricMatrices(n), **kwargs)
        self.n = n

    def belongs(self, mat, atol=gs.atol):
        """Check if a matrix is symmetric with positive eigenvalues.

        Parameters
        ----------
        mat : array-like, shape=[..., n, n]
            Matrix to be checked.
        atol : float
            Tolerance.
            Optional, default: backend atol.

        Returns
        -------
        belongs : array-like, shape=[...,]
            Boolean denoting if mat is an SPD matrix.
        """
        is_symmetric = self.ambient_space.belongs(mat, atol)
        eigvalues = gs.linalg.eigvalsh(mat)
        is_positive = gs.all(eigvalues > 0, axis=-1)
        belongs = gs.logical_and(is_symmetric, is_positive)
        return belongs

    def projection(self, point):
        """Project a matrix to the space of SPD matrices.

        First the symmetric part of point is computed, then the eigenvalues
        are floored to gs.atol.

        Parameters
        ----------
        point : array-like, shape=[..., n, n]
            Matrix to project.

        Returns
        -------
        projected: array-like, shape=[..., n, n]
            SPD matrix.
        """
        sym = Matrices.to_symmetric(point)
        eigvals, eigvecs = gs.linalg.eigh(sym)
        regularized = gs.where(eigvals < gs.atol, gs.atol, eigvals)
        reconstruction = gs.einsum('...ij,...j->...ij', eigvecs, regularized)
        return Matrices.mul(reconstruction, Matrices.transpose(eigvecs))

    def random_point(self, n_samples=1, bound=1.):
        """Sample in SPD(n) from the log-uniform distribution.

        Parameters
        ----------
        n_samples : int
            Number of samples.
            Optional, default: 1.
        bound : float
            Bound of the interval in which to sample in the tangent space.
            Optional, default: 1.

        Returns
        -------
        samples : array-like, shape=[..., n, n]
            Points sampled in SPD(n).
        """
        n = self.n
        size = (n_samples, n, n) if n_samples != 1 else (n, n)

        mat = bound * (2 * gs.random.rand(*size) - 1)
        spd_mat = GeneralLinear.exp(Matrices.to_symmetric(mat))

        return spd_mat

    def random_tangent_vec(self, n_samples=1, base_point=None):
        """Sample on the tangent space of SPD(n) from the uniform distribution.

        Parameters
        ----------
        n_samples : int
            Number of samples.
            Optional, default: 1.
        base_point : array-like, shape=[..., n, n]
            Base point of the tangent space.
            Optional, default: None.

        Returns
        -------
        samples : array-like, shape=[..., n, n]
            Points sampled in the tangent space at base_point.
        """
        n = self.n
        size = (n_samples, n, n) if n_samples != 1 else (n, n)

        if base_point is None:
            base_point = gs.eye(n)

        sqrt_base_point = gs.linalg.sqrtm(base_point)

        tangent_vec_at_id = 2 * gs.random.rand(*size) - 1
        tangent_vec_at_id += Matrices.transpose(tangent_vec_at_id)

        tangent_vec = Matrices.mul(
            sqrt_base_point, tangent_vec_at_id, sqrt_base_point)

        return tangent_vec

    @staticmethod
    def aux_differential_power(power, tangent_vec, base_point):
        """Compute the differential of the matrix power.

        Auxiliary function to the functions differential_power and
        inverse_differential_power.

        Parameters
        ----------
        power : float
            Power function to differentiate.
        tangent_vec : array_like, shape=[..., n, n]
            Tangent vector at base point.
        base_point : array_like, shape=[..., n, n]
            Base point.

        Returns
        -------
        eigvectors : array-like, shape=[..., n, n]
        transp_eigvectors : array-like, shape=[..., n, n]
        numerator : array-like, shape=[..., n, n]
        denominator : array-like, shape=[..., n, n]
        temp_result : array-like, shape=[..., n, n]
        """
        eigvalues, eigvectors = gs.linalg.eigh(base_point)

        if power == 0:
            powered_eigvalues = gs.log(eigvalues)
        elif power == math.inf:
            powered_eigvalues = gs.exp(eigvalues)
        else:
            powered_eigvalues = eigvalues**power

        denominator = eigvalues[..., :, None] - eigvalues[..., None, :]
        numerator = (
            powered_eigvalues[..., :, None] - powered_eigvalues[..., None, :])

        if power == 0:
            numerator = gs.where(
                denominator == 0, gs.ones_like(numerator), numerator)
            denominator = gs.where(
                denominator == 0, eigvalues[..., :, None], denominator)
        elif power == math.inf:
            numerator = gs.where(
                denominator == 0, powered_eigvalues[..., :, None], numerator)
            denominator = gs.where(
                denominator == 0, gs.ones_like(numerator), denominator)
        else:
            numerator = gs.where(
                denominator == 0,
                power * powered_eigvalues[..., :, None],
                numerator)
            denominator = gs.where(
                denominator == 0,
                eigvalues[..., :, None],
                denominator)

        transp_eigvectors = Matrices.transpose(eigvectors)
        temp_result = Matrices.mul(transp_eigvectors, tangent_vec, eigvectors)

        return (
            eigvectors, transp_eigvectors, numerator, denominator, temp_result)

    @classmethod
    def differential_power(cls, power, tangent_vec, base_point):
        r"""Compute the differential of the matrix power function.

        Compute the differential of the power function on SPD(n)
        (:math: `A^p=\exp(p \log(A))`) at base_point applied to tangent_vec.

        Parameters
        ----------
        power : int
            Power.
        tangent_vec : array_like, shape=[..., n, n]
            Tangent vector at base point.
        base_point : array_like, shape=[..., n, n]
            Base point.

        Returns
        -------
        differential_power : array-like, shape=[..., n, n]
            Differential of the power function.
        """
        eigvectors, transp_eigvectors, numerator, denominator, temp_result =\
            cls.aux_differential_power(power, tangent_vec, base_point)
        power_operator = numerator / denominator
        result = power_operator * temp_result
        result = Matrices.mul(eigvectors, result, transp_eigvectors)
        return result

    @classmethod
    def inverse_differential_power(cls, power, tangent_vec, base_point):
        r"""Compute the inverse of the differential of the matrix power.

        Compute the inverse of the differential of the power
        function on SPD matrices (:math: `A^p=exp(p log(A))`) at base_point
        applied to tangent_vec.

        Parameters
        ----------
        power : int
            Power.
        tangent_vec : array_like, shape=[..., n, n]
            Tangent vector at base point.
        base_point : array_like, shape=[..., n, n]
            Base point.

        Returns
        -------
        inverse_differential_power : array-like, shape=[..., n, n]
            Inverse of the differential of the power function.
        """
        eigvectors, transp_eigvectors, numerator, denominator, temp_result =\
            cls.aux_differential_power(power, tangent_vec, base_point)
        power_operator = denominator / numerator
        result = power_operator * temp_result
        result = Matrices.mul(eigvectors, result, transp_eigvectors)
        return result

    @classmethod
    def differential_log(cls, tangent_vec, base_point):
        """Compute the differential of the matrix logarithm.

        Compute the differential of the matrix logarithm on SPD
        matrices at base_point applied to tangent_vec.

        Parameters
        ----------
        tangent_vec : array_like, shape=[..., n, n]
            Tangent vector at base point.
        base_point : array_like, shape=[..., n, n]
            Base point.

        Returns
        -------
        differential_log : array-like, shape=[..., n, n]
            Differential of the matrix logarithm.
        """
        eigvectors, transp_eigvectors, numerator, denominator, temp_result =\
            cls.aux_differential_power(0, tangent_vec, base_point)
        power_operator = numerator / denominator
        result = power_operator * temp_result
        result = Matrices.mul(eigvectors, result, transp_eigvectors)
        return result

    @classmethod
    def inverse_differential_log(cls, tangent_vec, base_point):
        """Compute the inverse of the differential of the matrix logarithm.

        Compute the inverse of the differential of the matrix
        logarithm on SPD matrices at base_point applied to
        tangent_vec.

        Parameters
        ----------
        tangent_vec : array_like, shape=[..., n, n]
            Tangent vector at base point.
        base_point : array_like, shape=[..., n, n]
            Base point.

        Returns
        -------
        inverse_differential_log : array-like, shape=[..., n, n]
            Inverse of the differential of the matrix logarithm.
        """
        eigvectors, transp_eigvectors, numerator, denominator, temp_result =\
            cls.aux_differential_power(0, tangent_vec, base_point)
        power_operator = denominator / numerator
        result = power_operator * temp_result
        result = Matrices.mul(eigvectors, result, transp_eigvectors)
        return result

    @classmethod
    def differential_exp(cls, tangent_vec, base_point):
        """Compute the differential of the matrix exponential.

        Computes the differential of the matrix exponential on SPD
        matrices at base_point applied to tangent_vec.

        Parameters
        ----------
        tangent_vec : array_like, shape=[..., n, n]
            Tangent vector at base point.
        base_point : array_like, shape=[..., n, n]
            Base point.

        Returns
        -------
        differential_exp : array-like, shape=[..., n, n]
            Differential of the matrix exponential.
        """
        eigvectors, transp_eigvectors, numerator, denominator, temp_result = \
            cls.aux_differential_power(math.inf, tangent_vec, base_point)
        power_operator = numerator / denominator
        result = power_operator * temp_result
        result = Matrices.mul(eigvectors, result, transp_eigvectors)
        return result

    @classmethod
    def inverse_differential_exp(cls, tangent_vec, base_point):
        """Compute the inverse of the differential of the matrix exponential.

        Computes the inverse of the differential of the matrix
        exponential on SPD matrices at base_point applied to
        tangent_vec.

        Parameters
        ----------
        tangent_vec : array_like, shape=[..., n, n]
            Tangent vector at base point.
        base_point : array_like, shape=[..., n, n]
            Base point.

        Returns
        -------
        inverse_differential_exp : array-like, shape=[..., n, n]
            Inverse of the differential of the matrix exponential.
        """
        eigvectors, transp_eigvectors, numerator, denominator, temp_result = \
            cls.aux_differential_power(math.inf, tangent_vec, base_point)
        power_operator = denominator / numerator
        result = power_operator * temp_result
        result = Matrices.mul(eigvectors, result, transp_eigvectors)
        return result

    @classmethod
    def logm(cls, mat):
        """
        Compute the matrix log for a symmetric matrix.

        Parameters
        ----------
        mat : array_like, shape=[..., n, n]
            Symmetric matrix.

        Returns
        -------
        log : array_like, shape=[..., n, n]
            Matrix logarithm of mat.
        """
        n = mat.shape[-1]
        dim_3_mat = gs.reshape(mat, [-1, n, n])
        logm = SymmetricMatrices.apply_func_to_eigvals(
            dim_3_mat, gs.log, check_positive=True)
        logm = gs.reshape(logm, mat.shape)
        return logm

    expm = SymmetricMatrices.expm
    powerm = SymmetricMatrices.powerm
    from_vector = SymmetricMatrices.__dict__['from_vector']
    to_vector = SymmetricMatrices.__dict__['to_vector']

