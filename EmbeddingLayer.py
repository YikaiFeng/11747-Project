import torch
import numpy as np
import torch.nn as nn


class InputEmbeddingLayer(torch.nn.Module):
    def __init__(self, W_init, config):
        super(InputEmbeddingLayer, self).__init__()

        self.num_token = W_init.shape[0]
        self.embed_dim = W_init.shape[1]
        self.char_dim = config["char_dim"]
        self.num_chars = config["num_characters"]
        self.char_filter_size = config["char_filter_size"]
        self.char_filter_width = config["char_filter_width"]

        token_emb_lookup = self.get_token_embedding(W_init)
        char_emb_lookup = self.get_char_embedding()


    def get_token_embedding(self, W_init):
        token_embedding = nn.Embedding(self.num_token, self.embed_dim)
        token_embedding.weight.data.copy_(torch.from_numpy(W_init))
        return token_embedding

    def get_char_embedding(self):
        char_embed_init = np.random.uniform(0.0, 1.0, (self.num_chars, self.char_dim))
        char_emb = nn.Embedding(self.num_chars, self.char_dim)
        char_emb.weight.data.copy_(torch.from_numpy(char_embed_init))
        return char_emb

