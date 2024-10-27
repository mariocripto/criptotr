#!/usr/bin/env python3
# Copyright (c) 2014-2016 The Bitcoin Core developers
# Copyright (c) 2022 The Dogecoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

#
# Test RPC calls related to blockchain state. Tests correspond to code in
# rpc/blockchain.cpp.
#

from decimal import Decimal

from test_framework.test_framework import BitcoinTestFramework
from test_framework.authproxy import JSONRPCException
from test_framework.util import (
    assert_equal,
    assert_greater_than,
    assert_greater_than_or_equal,
    assert_raises,
    assert_is_hex_string,
    assert_is_hash_string,
    start_nodes,
    start_node,
    connect_nodes_bi,
)


class BlockchainTest(BitcoinTestFramework):
    """
    Test blockchain-related RPC calls:

        - gettxoutsetinfo
        - getutxoforkey
        - verifychain

    """

    def __init__(self):
        super().__init__()
        self.setup_clean_chain = False
        self.num_nodes = 2

    def setup_network(self, split=False):
        self.nodes = []
        self.nodes.append(start_node(0, self.options.tmpdir, ["-prune=1"]))
        self.nodes.append(start_node(1, self.options.tmpdir, ["-prune=2200"]))
        connect_nodes_bi(self.nodes, 0, 1)
        self.is_network_split = False
        self.sync_all()

    def run_test(self):
        self._test_gettxoutsetinfo()
        self._test_getutxoforkey()
        self._test_getblockheader()
        self._test_getblockchaininfo()
        self._test_verifychain_args()
        self.nodes[0].verifychain(4, 0)

    # PL backported this entire test from upstream 0.16 to 1.14.3
    def _test_getblockchaininfo(self):

        keys = [
            'bestblockhash',
            'bip9_softforks',
            'blocks',
            'chain',
            'chainwork',
            'difficulty',
            'headers',
            'initialblockdownload',
            'mediantime',
            'pruned',
            'size_on_disk',
            'softforks',
            'verificationprogress',
            'warnings',
        ]
        res = self.nodes[0].getblockchaininfo()

        # result should have these additional pruning keys if manual pruning is enabled
        assert_equal(sorted(res.keys()), sorted(['pruneheight', 'automatic_pruning'] + keys))

        # size_on_disk should be > 0
        assert_greater_than(res['size_on_disk'], 0)

        # pruneheight should be greater or equal to 0
        assert_greater_than_or_equal(res['pruneheight'], 0)

        # check other pruning fields given that prune=1
        assert res['pruned']
        assert not res['automatic_pruning']

        res = self.nodes[1].getblockchaininfo()
        # result should have these additional pruning keys if prune=2200
        assert_equal(sorted(res.keys()), sorted(['pruneheight', 'automatic_pruning', 'prune_target_size'] + keys))

        # check related fields
        assert res['pruned']
        assert_equal(res['pruneheight'], 0)
        assert res['automatic_pruning']
        assert_equal(res['prune_target_size'], 2306867200)
        assert_greater_than(res['size_on_disk'], 0)

    def _test_gettxoutsetinfo(self):
        node = self.nodes[0]
        res = node.gettxoutsetinfo()

        assert_equal(res['total_amount'], Decimal('60000000.00000000'))
        assert_equal(res['transactions'], 120)
        assert_equal(res['height'], 120)
        assert_equal(res['txouts'], 120)
        assert_equal(res['bytes_serialized'], 8520),
        assert_equal(len(res['bestblock']), 64)
        assert_equal(len(res['hash_serialized']), 64)

    def _test_getutxoforkey(self):
        
        # check for invalid private key input
        try:
            self.nodes[0].getutxoforkey("")
        except JSONRPCException as e:
            assert("Invalid private key encoding" in e.error["message"])

        address = self.nodes[0].getnewaddress()
        privkey = self.nodes[0].dumpprivkey(address)

        amount = 42.001
        txid = self.nodes[1].sendtoaddress(address, amount)

        # Node1 sends 42.001 Doge to node0, then node1 mines a block.
        # At this point nodes are not yet synchronized and calling 
        # getutxoforkey with private key on node0 will throw an exception.
        self.nodes[1].generate(1)
 
        try: 
            res = self.nodes[0].getutxoforkey(privkey)
        except JSONRPCException as e:
            assert("Unable to find utxo amount")      
 
        # at this point utxo record is available on node1

        res = self.nodes[1].getutxoforkey(privkey)

        # verify that txid, utxo amount and new block height for tx 
        # with 42.001 Doges is the same as in this RPC response
        assert_equal(res['amount'], Decimal("42.001"))
        assert_equal(res['height'], 121)
        assert_equal(res['txid'], txid)

        # NOTE: calling self.sync_all() results in assertion failure
        # 'Block sync to height 121 timed out' so as a workaround we
        # currently check the presense of utxo only on node1

    def _test_getblockheader(self):
        node = self.nodes[0]

        assert_raises(
            JSONRPCException, lambda: node.getblockheader('nonsense'))

        besthash = node.getbestblockhash()
        secondbesthash = node.getblockhash(119)
        header = node.getblockheader(besthash)

        assert_equal(header['hash'], besthash)
        assert_equal(header['height'], 120)
        assert_equal(header['confirmations'], 1)
        assert_equal(header['previousblockhash'], secondbesthash)
        assert_is_hex_string(header['chainwork'])
        assert_is_hash_string(header['hash'])
        assert_is_hash_string(header['previousblockhash'])
        assert_is_hash_string(header['merkleroot'])
        assert_is_hash_string(header['bits'], length=None)
        assert isinstance(header['time'], int)
        assert isinstance(header['mediantime'], int)
        assert isinstance(header['nonce'], int)
        assert isinstance(header['version'], int)
        assert isinstance(int(header['versionHex'], 16), int)
        assert isinstance(header['difficulty'], Decimal)

    def _test_verifychain_args(self):
        node = self.nodes[0]

        try:
            node.verifychain(-1)
            raise AssertionError("Must check for validity of checklevel parameter")
        except JSONRPCException as e:
            assert("Error: checklevel must be >= 0 and <= 4" in e.error["message"])

        try:
            node.verifychain(5)
            raise AssertionError("Must check for validity of checklevel parameter")
        except JSONRPCException as e:
            assert("Error: checklevel must be >= 0 and <= 4" in e.error["message"])

        try:
            node.verifychain(0, -100)
            raise AssertionError("Must check for validity of nblocks parameter")
        except JSONRPCException as e:
            assert("Error: nblocks must be >= 0" in e.error["message"])

        try:
            node.verifychain(0, -1000)
            raise AssertionError("Must check for validity of nblocks parameter")
        except JSONRPCException as e:
            assert("Error: nblocks must be >= 0" in e.error["message"])

if __name__ == '__main__':
    BlockchainTest().main()
