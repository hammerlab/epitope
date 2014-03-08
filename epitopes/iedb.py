# Copyright (c) 2014. Mount Sinai School of Medicine
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from os.path import join

import numpy as np
import pandas as pd

from base import DATA_DIR
from features import make_ngram_dataset
from common import split_classes, bad_amino_acids

TCELL_CSV = join(DATA_DIR, 'tcell_compact.csv')
MHC_CSV = join(DATA_DIR, 'elution_compact.csv')

def _load_dataframe(
        filename,
        human = True,
        mhc_class = None, # 1, 2, or None for both
        hla_type = None, # regex pattern i.e. '(HLA-A2)|(HLA-A\*02)'
        exclude_hla_type = None, # regex pattern i.e. '(HLA-A2)|(HLA-A\*02)'
        peptide_length = None,
        assay_group=None,
        nrows = None,
        reduced_alphabet = None,
        verbose= True):
    """
    Load an IEDB csv into a pandas dataframe and filter using the
    criteria given as function arguments
    """
    df = pd.read_csv(filename, skipinitialspace=True, nrows = nrows)
    mhc = df['MHC Allele Name']

    #
    # Match known alleles such as 'HLA-A*02:01',
    # broader groupings such as 'HLA-A2'
    # and unknown alleles of the MHC-1 listed either as
    #  'HLA-Class I,allele undetermined'
    #  or
    #  'Class I,allele undetermined'
    mhc1_pattern = 'Class I,|HLA-[A-C]([0-9]|\*)'
    mhc1_mask = mhc.str.contains(mhc1_pattern, na=False).astype('bool')

    mhc2_pattern = "Class II,|HLA-D(P|M|O|Q|R)"
    mhc2_mask = mhc.str.contains(mhc2_pattern, na=False).astype('bool')

    # just in case any of the results were from mice or other species,
    # restrict to humans
    organism = df['Host Organism Name']
    human_organism_mask = \
        organism.str.startswith('Homo sapiens', na=False).astype('bool')
    human_hla_mask = mhc.str.startswith("HLA", na=False).astype('bool')
    human_mask = human_organism_mask | human_hla_mask

    if verbose:
        print "Human entries", human_mask.sum()
        print "Class I MHC Entries", mhc1_mask.sum()
        print "Class II MHC Entries", mhc2_mask.sum()
        print "Human Class I MHCs", (human_mask & mhc1_mask).sum()
        print "Human Class II MHCs", (human_mask & mhc2_mask).sum()

    epitopes = df['Epitope Linear Sequence'].str.upper()
    if reduced_alphabet:
        def transform(s):
            return ''.join([chr(48 + reduced_alphabet[char]) for char in s])
        epitopes = epitopes.map(transform)
    df['Epitope Linear Sequence'] = epitopes
    null_epitope_seq = epitopes.isnull()


    # if have rare or unknown amino acids, drop the sequence
    bad_epitope_seq = \
        epitopes.str.contains(bad_amino_acids, na=False).astype('bool')

    if verbose:
        print "Dropping %d null sequences" % null_epitope_seq.sum()
        print "Dropping %d bad sequences" % bad_epitope_seq.sum()

    has_epitope_seq = ~(bad_epitope_seq | null_epitope_seq)

    mask = has_epitope_seq

    if human:
        mask &= human_mask
    if mhc_class == 1:
        mask &= mhc1_mask
    if mhc_class == 2:
        mask &= mhc2_mask

    if assay_group:
        mask &= df['Assay Group'] == assay_group

    if hla_type:
        mask &= mhc.str.contains(hla_type, na=False)

    if exclude_hla_type:
        mask &= ~mhc.str.contains(exclude_hla_type, na=False)

    if peptide_length:
        assert peptide_length > 0
        mask &=  epitopes.str.len() == peptide_length

    if verbose:
        print "Filtered sequences epitope sequences", mask.sum()

    return df[mask]

def _group_epitopes(
        df,
        unique_sequences = True,
        min_count = 0,
        group_by_allele = False,
        verbose = True):
    """
    Given a dataframe of epitopes and qualitative measures,
    group the epitope strings (optionally also grouping by allele),
    and associate each group with its percentage of Positive
    Qualitative Measure results.
    """
    epitopes = df['Epitope Linear Sequence']
    measure = df['Qualitative Measure']
    mhc = df['MHC Allele Name']
    pos_mask = measure.str.startswith('Positive').astype('bool')

    if group_by_allele:
        groups = pos_mask.groupby([epitopes, mhc])
    else:
        groups = pos_mask.groupby(epitopes)

    values = groups.mean()

    if min_count:
        counts = groups.count()
        values = values[counts >= min_count]

    return values



def load_tcell(
        mhc_class = None, # 1, 2, or None for neither
        hla_type = None,
        exclude_hla_type = None,
        peptide_length = None,
        assay_group=None,
        reduced_alphabet = None, # 20 letter AA strings -> simpler alphabet
        nrows = None,
        verbose= True):
    """
    Load IEDB T-cell data without aggregating multiple entries for same epitope

    Parameters
    ----------
    mhc_class: {None, 1, 2}
        Restrict to MHC Class I or Class II (or None for neither)

    hla_type: regex pattern, optional
        Restrict results to specific HLA type used in assay

    exclude_hla_type: regex pattern, optional
        Exclude certain HLA types

    peptide_length: int, optional
        Restrict epitopes to amino acid strings of given length

    assay_group: string, optional
        Only collect results from assays of the given type

    nrows: int, optional
        Don't load the full IEDB dataset but instead read only the first nrows

    reduced_alphabet: dictionary, optional
        Remap amino acid letters to some other alphabet

    verbose: bool
        Print debug output
    """


    return _load_dataframe(
            TCELL_CSV,
            assay_group = assay_group,
            mhc_class = mhc_class,
            hla_type = hla_type,
            exclude_hla_type = exclude_hla_type,
            peptide_length = peptide_length,
            reduced_alphabet = reduced_alphabet,
            nrows = nrows,
            verbose = verbose)


def load_tcell_values(
        mhc_class = None, # 1, 2, or None for neither
        hla_type = None,
        exclude_hla_type = None,
        peptide_length = None,
        assay_group=None,
        reduced_alphabet = None, # 20 letter AA strings -> simpler alphabet
        nrows = None,
        min_count = 0,
        group_by_allele = False,
        verbose= True):
    """
    Load the T-cell response data from IEDB, collect into a dataframe mapping
    epitopes to percentage positive results.

    Parameters
    ----------
    mhc_class: {None, 1, 2}
        Restrict to MHC Class I or Class II (or None for neither)

    hla_type: regex pattern, optional
        Restrict results to specific HLA type used in assay

    exclude_hla_type: regex pattern, optional
        Exclude certain HLA types

    peptide_length: int, optional
        Restrict epitopes to amino acid strings of given length

    assay_group: string, optional
        Only collect results from assays of the given type

    reduced_alphabet: dictionary, optional
        Remap amino acid letters to some other alphabet

    nrows: int, optional
        Don't load the full IEDB dataset but instead read only the first nrows

    group_by_allele:
        Don't combine epitopes across multiple HLA types

    min_count: int, optional
        Exclude epitopes which appear fewer times than min_count

    verbose: bool
        Print debug output
    """

    df = load_tcell_dataframe(
        mhc_class = mhc_class,
        hla_type = hla_type,
        exclude_hla_type = exclude_hla_type,
        peptide_length = peptide_length,
        assay_group = assay_group,
        reduced_alphabet = reduced_alphabet,
        nrows = nrows,
        verbose = verbose)

    return _group_epitopes(
            df,
            group_by_allele = group_by_allele,
            min_count = min_count,
            verbose = verbose)

def load_tcell_classes(*args, **kwargs):
    """
    Split the T-cell assay results into positive and negative sets.

    Parameters
    ----------
    noisy_labels : {'majority', 'negative', 'positive'}
        Which class do we assign an epitope with contradictory labels?

    *args, **kwargs : same as 'load_tcell'
    """
    noisy_labels = kwargs.pop('noisy_labels', None)
    verbose = kwargs.get('verbose')
    tcell_values = load_tcell_values(*args, **kwargs)
    return split_classes(
        tcell_values,
        noisy_labels = noisy_labels,
        verbose = verbose)

def load_tcell_ngrams(*args, **kwargs):
    """
    Construct n-gram input features X and output labels Y for T-cell responses

    Parameters:
    ----------
    ngram : int
        Order of n-grams to consider when constructing X.
        For example, when ngram = 1, the vector space is the individual
        frequencies of letters in the amino acid strings.

    normalize_row : bool, optional
        If True (default), then return frequencies, else raw counts.

    subsample_bigger_class: bool, optional
        When the number of samples in both classes are unbalanced,
        randomly drop some samples from the larger class (default = False).

    return_transformer: bool
        Return `X, Y, f` instead of just `X, Y`,
        where f can be used to transform new amino acid strings into
        the same space as the training data.


    *args, **kwargs : same as `load_tcell_classes`
    """

    ngram = kwargs.pop('ngram', 1)
    normalize_row = kwargs.pop('normalize_row', True)
    subsample_bigger_class = kwargs.pop('subsample_bigger_class', False)
    return_transformer = kwargs.pop('return_transformer', False)
    verbose = kwargs.get('verbose')

    pos, neg = load_tcell_classes(*args, **kwargs)
    return make_ngram_dataset(
        pos,
        neg,
        max_ngram = ngram,
        normalize_row = normalize_row,
        subsample_bigger_class = subsample_bigger_class,
        return_transformer = return_transformer)

def load_mhc(
        mhc_class = None, # 1, 2, or None for neither
        hla_type = None,
        exclude_hla_type = None,
        peptide_length = None,
        assay_group=None,
        reduced_alphabet = None, # 20 letter AA strings -> simpler alphabet
        nrows = None,
        verbose = True):
    """
    Load IEDB MHC data without aggregating multiple entries for the same epitope
    """
    return _load_dataframe(
                MHC_CSV,
                mhc_class = mhc_class,
                hla_type = hla_type,
                exclude_hla_type = exclude_hla_type,
                peptide_length = peptide_length,
                assay_group = assay_group,
                reduced_alphabet = reduced_alphabet,
                nrows = nrows,
                verbose = verbose)


def load_mhc_values(
        mhc_class = None, # 1, 2, or None for neither
        hla_type = None,
        exclude_hla_type = None,
        peptide_length = None,
        assay_group=None,
        reduced_alphabet = None, # 20 letter AA strings -> simpler alphabet
        nrows = None,
        group_by_allele = False,
        min_count = 0,
        verbose= True):
    """
    Load the MHC binding results from IEDB, collect into a dataframe mapping
    epitopes to percentage positive results.

    Parameters
    ----------
    mhc_class: {None, 1, 2}
        Restrict to MHC Class I or Class II (or None for neither)

    hla_type: regex pattern, optional
        Restrict results to specific HLA type used in assay

    exclude_hla_type: regex pattern, optional
        Exclude certain HLA types

    peptide_length: int, optional
        Restrict epitopes to amino acid strings of given length

    assay_group: string, optional
        Only collect results from assays of the given type

    reduced_alphabet: dictionary, optional
        Remap amino acid letters to some other alphabet

    nrows: int, optional
        Don't load the full IEDB dataset but instead read only the first nrows

    group_by_allele:
        Don't combine epitopes across multiple HLA types

    min_count: int, optional
        Exclude epitopes which appear fewer times than min_count

    verbose: bool
        Print debug output
    """
    df = load_mhc(
        mhc_class = mhc_class,
        hla_type = hla_type,
        exclude_hla_type = exclude_hla_type,
        peptide_length = peptide_length,
        assay_group = assay_group,
        reduced_alphabet = reduced_alphabet,
        nrows = nrows,
        verbose = verbose)

    return _group_epitopes(
            df,
            group_by_allele = group_by_allele,
            min_count = min_count,
            verbose = verbose)

def load_mhc_classes(*args, **kwargs):
    """
    Split the MHC binding assay results into positive and negative sets.

    Parameters
    ----------
    noisy_labels : 'majority' | 'negative' | 'positive'
        Which class do we assign an epitope with contradictory labels?

    *args, **kwargs : same as 'load_tcell'
    """
    noisy_labels = kwargs.pop('noisy_labels', None)
    verbose = kwargs.get('verbose')
    mhc_values = load_mhc(*args, **kwargs)
    return split_classes(
        mhc_values,
        noisy_labels = noisy_labels,
        verbose = verbose)

def load_mhc_ngrams(*args, **kwargs):
    """
    Construct n-gram input features X and output labels Y for MHC binding

    Parameters:
    ----------
    ngram : int
        Order of n-grams to consider when constructing X.
        For example, when ngram = 1, the vector space is the individual
        frequencies of letters in the amino acid strings.

    normalize_row : bool, optional
        If True (default), then return frequencies, else raw counts.

    subsample_bigger_class: bool, optional
        When the number of samples in both classes are unbalanced,
        randomly drop some samples from the larger class (default = False).

    return_transformer: bool
        Return `X, Y, f` instead of just `X, Y`,
        where f can be used to transform new amino acid strings into
        the same space as the training data.


    *args, **kwargs : same as `load_tcell_classes`
    """

    ngram = kwargs.pop('ngram', 1)
    normalize_row = kwargs.pop('normalize_row', True)
    subsample_bigger_class = kwargs.pop('subsample_bigger_class', False)
    return_transformer = kwargs.pop('return_transformer', False)
    verbose = kwargs.get('verbose')

    pos, neg = load_mhc_classes(*args, **kwargs)
    return make_ngram_dataset(
        pos,
        neg,
        max_ngram = ngram,
        normalize_row = normalize_row,
        subsample_bigger_class = subsample_bigger_class,
        return_transformer = return_transformer)


def load_tcell_vs_mhc(
        mhc_class = None, # 1, 2, or None for neither
        hla_type = None,
        exclude_hla_type = None,
        peptide_length = None,
        min_count = 0,
        assay_group=None,
        nrows = None,
        group_by_allele = False,
        verbose= True):
    """
    Percentage positive results for both T-cell response assays
    and MHC binding assays (keyed by epitopes for which we have data
    for both)
    """
    mhc = load_mhc_values(
            mhc_class = mhc_class,
            hla_type = hla_type,
            exclude_hla_type = exclude_hla_type,
            peptide_length = peptide_length,
            assay_group=assay_group,
            nrows = nrows,
            min_count = min_count,
            group_by_allele = group_by_allele,
            verbose = verbose)
    tcell = load_tcell_values(
                mhc_class = mhc_class,
                hla_type = hla_type,
                exclude_hla_type = exclude_hla_type,
                assay_group=assay_group,
                peptide_length = peptide_length,
                nrows = nrows,
                min_count = min_count,
                group_by_allele = group_by_allele,
                verbose = verbose)
    df_combined = pd.DataFrame({'mhc':mhc, 'tcell':tcell})
    both = ~(df_combined.mhc.isnull() | df_combined.tcell.isnull())
    return df_combined[both]
