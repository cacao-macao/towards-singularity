import numpy as np
from layers import *


"""
A model for sequence-to-sequence learning.
The model is based on an encoder-decoder architecture with attention mechanism.
A recurrent neural network is used to encode the source sentence into a single
vector. This vector is then decoded by a second RNN which learns to output the
target sentence by generating it one word at a time.
Words generated by the decoder are inferenced based not only on the current
decoder hidden state, but also on an attention output calculeted using a weighted
sum over the encoder hidden states.
"""
class Seq2Seq(object):
    def __init__(self, src_seq_len, src_vocab_size, src_embed_dim,
                 trg_seq_len, trg_vocab_size, trg_embed_dim,
                 hidden_dim, null_idx, start_idx, end_idx,
                 attention=False, n_layers=1, cell_type="lstm", dtype=np.float32):
        """
        Inputs:
        - src_seq_len: Length of source sequence.
        - src_vocab_size: Vocab size of the source language.
        - src_embed_dim: Embedding dimensions of the source language.
        - trg_seq_len: Length of target sequence.
        - trg_vocab_size: Vocab size of the target language.
        - trg_embed_dim: Embedding dimensions of the target language.
        - hidden_dim: Dimension of the hidden state of the RNNs.
        - null_idx: Index of the "<NULL>" token.
        - start_idx: Index of the "<START>" token.
        - end_idx: Index of the "<END>" token.
        - attention: Boolean, indication weather attention mechanism should be used.
          Default value is False (no attention).
        - n_layers: Number of layers of the RNNs.
        - cell_type: What type of cell non-linearity to use: "rnn" or "lstm".
        - dtype: numpy datatype to use for computation.
        """
        self.src_seq_len = src_seq_len
        self.src_vocab_size = src_vocab_size
        self.src_embed_dim = src_embed_dim

        self.trg_seq_len = trg_seq_len
        self.trg_vocab_size = trg_vocab_size
        self.trg_embed_dim = trg_embed_dim

        self.hidden_dim = hidden_dim

        self.null_idx = null_idx
        self.start_idx = start_idx
        self.end_idx = end_idx

        self.attention = attention
        self.n_layers = n_layers
        self.cell_type = cell_type
        self.dtype = dtype
        self.params = {}

        # Initialize the weights and biases.
        self.params["W_embed_enc"] = np.random.randn(src_vocab_size, src_embed_dim) / np.sqrt(src_vocab_size)
        self.params["W_embed_dec"] = np.random.randn(trg_vocab_size, trg_embed_dim) / np.sqrt(trg_vocab_size)

        dim_mul = {"lstm": 4, "rnn": 1}[cell_type]
        for i in range(n_layers):
            self.params["Wx_%d_enc" % i] = np.random.randn(hidden_dim, dim_mul * hidden_dim) / np.sqrt(hidden_dim)
            self.params["Wh_%d_enc" % i] = np.random.randn(hidden_dim, dim_mul * hidden_dim) / np.sqrt(hidden_dim)
            self.params["b_%d_enc" % i] = np.zeros(dim_mul * hidden_dim)

            self.params["Wx_%d_dec" % i] = np.random.randn(hidden_dim, dim_mul * hidden_dim) / np.sqrt(hidden_dim)
            self.params["Wh_%d_dec" % i] = np.random.randn(hidden_dim, dim_mul * hidden_dim) / np.sqrt(hidden_dim)
            self.params["b_%d_dec" % i] = np.zeros(dim_mul * hidden_dim)

        self.params["Wx_0_enc"] = np.random.randn(src_embed_dim, dim_mul * hidden_dim) / np.sqrt(src_embed_dim)
        self.params["Wx_0_dec"] = np.random.randn(trg_embed_dim, dim_mul * hidden_dim) / np.sqrt(trg_embed_dim)

        dim_mul = 2 if attention else 1
        self.params["W_out_dec"] = np.random.randn(dim_mul * hidden_dim, trg_vocab_size) / np.sqrt(dim_mul * hidden_dim)
        self.params["b_out_dec"] = np.zeros(trg_vocab_size)

        # Cast all parameters to the correct datatype.
        for k, v in self.params.items():
            self.params[k] = v.astype(dtype)


    def _forward(self, src, trg):
        """
        Inputs:
        - src: A numpy array of integers (N, T_enc).
        - trg: A numpy array of integers shape (N, T_dec).

        Returns:
        - scores: A numpy array of shape (N, T_dec, trg_vocab_size) assigning scores
          to every word in the vocabulary of the target language.
        - caches: Values needed for the backward pass.
        """
        N, _= src.shape
        H = self.hidden_dim

        # Compute the embedings of the source words.
        src_embeds, enc_embed_cache = word_embedding_forward(src, self.params["W_embed_enc"])

        # Run through the encoder and calculate the context vector.
        z = np.ndarray((N, self.n_layers, H))
        h0 = np.zeros((N, H))
        h_enc = src_embeds
        enc_caches = []
        for i in range(self.n_layers):
            if self.cell_type == "rnn":
                h_enc, cache = recurrent_forward(h_enc, h0, self.params["Wx_%d_enc" % i], self.params["Wh_%d_enc" % i],
                                                 self.params["b_%d_enc" % i])
            elif self.cell_type == "lstm":
                h_enc, cache = lstm_forward(h_enc, h0, self.params["Wx_%d_enc" % i], self.params["Wh_%d_enc" % i],
                                            self.params["b_%d_enc" % i])
            enc_caches.append(cache)
            z[:, i, :] = h_enc[:, -1, :]


        # Compute the embeddings of the target words.
        trg_embeds, dec_embed_cache = word_embedding_forward(trg, self.params["W_embed_dec"])

        # Run through the decoder and get the scores.
        h_dec = trg_embeds
        dec_caches = []
        for i in range(self.n_layers):
            h0 = z[:, i, :].reshape(N, H)
            if self.cell_type == "rnn":
                h_dec, cache = recurrent_forward(h_dec, h0, self.params["Wx_%d_dec" % i], self.params["Wh_%d_dec" % i],
                                                 self.params["b_%d_dec" % i])
            elif self.cell_type == "lstm":
                h_dec, cache = lstm_forward(h_dec, h0, self.params["Wx_%d_dec" % i], self.params["Wh_%d_dec" % i],
                                            self.params["b_%d_dec" % i])
            dec_caches.append(cache)

        # Compute the attenton outputs.
        att_out, att_cache = temporal_attention_forward(h_dec, h_enc)

        # Use the attention output only if flag is raised.
        if (self.attention):
            dec_out = np.append(h_dec, att_out, axis=-1)
        else:
            dec_out = h_dec

        # Compute the decoder output.
        scores, dec_out_cache = temporal_affine_forward(dec_out, self.params["W_out_dec"], self.params["b_out_dec"])
        caches = (enc_embed_cache, enc_caches, dec_embed_cache, dec_caches, att_cache, dec_out_cache)

        return scores, caches


    def _backward(self, dscores, caches):
        """
        Inputs:
        - dscores: Upstream derivatives of the scores of shape (N, T_dec, M).
        - caches: Cached variables for the backward pass.

        Returns:
        - grads: Dictionary with the same keys as self.params, mapping parameter
          names to gradients of the loss with respect to those parameters.
        """
        N, T_dec, M = dscores.shape
        T_enc = self.src_seq_len
        H = self.hidden_dim
        grads = {}

        enc_embed_cache, enc_caches, dec_embed_cache, dec_caches, att_cache, dec_out_cache = caches
        d_dec_out, dW_out, db_out = temporal_affine_backward(dscores, dec_out_cache)

        grads["W_out_dec"] = dW_out
        grads["b_out_dec"] = db_out

        # Backprop through attention.
        if (self.attention):
            dh_dec = d_dec_out[:, :, : H]
            datt_out = d_dec_out[:, :, H : ]
            dh_dec_temp, dh_enc = temporal_attention_backward(datt_out, att_cache)
            dh_dec += dh_dec_temp
        else:
            dh_dec = d_dec_out
            dh_enc = np.zeros((N, T_enc, H))

        # Backprop through the decoder layers.
        dz = np.zeros((N, self.n_layers, H))
        for i in range(self.n_layers -1, -1, -1):
            if self.cell_type == "rnn":
                dh_dec, dh0, dWx, dWh, db = recurrent_backward(dh_dec, dec_caches.pop())
            elif self.cell_type == "lstm":
                dh_dec, dh0, dWx, dWh, db = lstm_backward(dh_dec, dec_caches.pop())

            grads["Wx_%d_dec" % i] = dWx
            grads["Wh_%d_dec" % i] = dWh
            grads["b_%d_dec" % i] = db

            dz[:, i, :] += dh0

        dW_embed_dec = word_embedding_backward(dh_dec, dec_embed_cache)
        grads["W_embed_dec"] = dW_embed_dec

        # Backprop through the encoder layers.
        for i in range(self.n_layers -1, -1, -1):
            dh_enc[:, -1, :] += dz[:, i, :]

            if self.cell_type == "rnn":
                dh_enc, dh0, dWx, dWh, db = recurrent_backward(dh_enc, enc_caches.pop())
            elif self.cell_type == "lstm":
                dh_enc, dh0, dWx, dWh, db = lstm_backward(dh_enc, enc_caches.pop())

            grads["Wx_%d_enc" % i] = dWx
            grads["Wh_%d_enc" % i] = dWh
            grads["b_%d_enc" % i] = db

        dW_embed_enc = word_embedding_backward(dh_enc, enc_embed_cache)
        grads["W_embed_enc"] = dW_embed_enc

        return grads


    def loss(self, src, trg):
        """
        Inputs:
        - src: A numpy array of integers (N, src_seq_len).
        - trg: A numpy array of integers shape (N, trg_seq_len).

        Returns:
        - loss: A scalar value giving the loss.
        - grads: Dictionary with the same keys as self.params, mapping parameter
          names to gradients of the loss with respect to those parameters.
        """
        trg_in = trg[:, :-1]
        trg_out = trg[:, 1:]

        # forward pass
        scores, caches = self._forward(src, trg_in)

        # compute the loss
        mask = (trg_out != self.null_idx)
        loss, dscores = temporal_cross_entropy_loss(scores, trg_out, mask)

        # backward pass
        grads = self._backward(dscores, caches)

        return loss, grads