import sys
import json
import numpy as np
import model2 as model
import EmbeddingLayer
import torch
import torch.nn as nn


config_path = "config.json"

# use GloVe pre-trained embedding
word_embedding_path = "GloVe/word2vec_glove.txt"

# vocab file for tokens in a specific dataset
vocab_path = "data/wikihop/vocab.txt"

# vocab file for chars in a specific dataset
vocab_char_path = "data/wikihop/vocab.txt.chars"

train_path = "data/wikihop/train_set.json"
valid_path = "data/wikihop/valid_set.json"

train_path = "data/wikihop/training_small.json"


def load_config(config_p):
    with open(config_p, 'r') as config_file:
        config = json.load(config_file)

    if config['stopping_criterion'] == 'True':
        config['stopping_criterion'] = True
    else:
        config['stopping_criterion'] = False

    return config


def build_dict(vocab_p, vocab_char_p):
    vocab_data = open(vocab_p, 'r').readlines()
    vocab_c_data = open(vocab_char_p, 'r').readlines()

    vocab_dict = {}  # key: token, val: cnt
    vocab_c_dict = {}  # key: char, val: cnt

    for one_line in vocab_data:
        tmp_list = one_line.rstrip('\n').split('\t')
        vocab_dict[tmp_list[0]] = int(tmp_list[1])

    for one_line in vocab_c_data:
        tmp_list = one_line.rstrip('\n').split('\t')
        vocab_c_dict[tmp_list[0]] = int(tmp_list[1])

    vocab_ordered_list = sorted(vocab_dict.items(), key=lambda item:item[1], reverse=True)
    vocal_c_ordered_list = sorted(vocab_c_dict.items(), key=lambda item:item[1], reverse=True)

    vocab_index_dict = {}  # key: token, val: index
    vocab_c_index_dict = {}  # key: char, val: index

    for index, one_tuple in enumerate(vocab_ordered_list):
        vocab_index_dict[one_tuple[0]] = index
    
    for index, one_tuple in enumerate(vocal_c_ordered_list):
        vocab_c_index_dict[one_tuple[0]] = index

    # test_out1 = open("tmp_word_dict.txt", 'w')
    # test_out2 = open("tmp_char_dict.txt", 'w')
    # for ele in vocab_index_dict:
    #     test_out1.writelines(str(ele) + '\t' + str(vocab_index_dict[ele]) + '\n')
    # for ele in vocab_c_index_dict:
    #     test_out2.writelines(str(ele) + '\t' + str(vocab_c_index_dict[ele]) + '\n')

    return vocab_index_dict, vocab_c_index_dict


def load_word2vec_embedding(w2v_p, vocab_dict):
    w2v_data = open(w2v_p, 'r').readlines()

    info = w2v_data[0].split()
    embed_dim = int(info[1])

    vocab_embed = {}  # key: token, value: embedding

    for line_index in range(1, len(w2v_data)):
        line = w2v_data[line_index].split()
        embed_part = [float(ele) for ele in line[1:]]
        vocab_embed[line[0]] = np.array(embed_part, dtype='float32')

    vocab_size = len(vocab_dict)
    W = np.random.randn(vocab_size, embed_dim).astype('float32')
    exist_cnt = 0

    for token in vocab_dict:
        if token in vocab_embed:
            token_index = vocab_dict[token]
            W[token_index,:] = vocab_embed[token]
            exist_cnt += 1

    print("%d/%d vocabs are initialized with word2vec embeddings." % (exist_cnt, vocab_size))
    return W, embed_dim


def get_doc_index_list(doc, token_dict, unk_dict):
    ret = []
    for token in doc:
        if token in token_dict:
            ret.append(token_dict[token])
        else:
            ret.append(unk_dict[token])
    return ret


def get_char_index_list(doc, char_dict, max_word_len):
    ret = []
    for token in doc:
        one_res = []
        for index in range(len(token)):
            one_char = token[index]
            if one_char in char_dict:
                one_res.append(char_dict[one_char])
            else:
                one_res.append(char_dict["__unkchar__"])
        ret.append(one_res[:max_word_len])
    return ret


def generate_examples(input_p, vocab_dict, vocab_c_dict, config):
    max_chains = config['max_chains']
    max_doc_len = config['max_doc_len']
    num_unks = config["num_unknown_types"]
    max_word_len = config["max_word_len"]

    ret = []

    with open(input_p, 'r') as infile:
        for index, one_line in enumerate(infile):
            data = json.loads(one_line.rstrip('\n'))

            doc_raw = data["document"].split()[:max_doc_len]
            qry_raw = data["query"].split()

            doc_lower = [t.lower() for t in doc_raw]
            qry_lower = [t.lower() for t in qry_raw]
            ans_lower = [t.lower() for t in data["answer"].split()]
            can_lower = [[t.lower() for t in cand] for cand in data["candidates"]]

            #------------------------------------------------------------------------
            # build oov dict for each example
            all_token = doc_lower + qry_lower + ans_lower
            for one_cand in can_lower:
                all_token += one_cand

            oov_set = set()
            for token in all_token:
                if token not in vocab_dict:
                    oov_set.add(token)

            unk_dict = {}  # key: token, val: index
            for ii, token in enumerate(oov_set):
                unk_dict[token] = vocab_dict["__unkword%d__" % (ii % num_unks)]
            
            #------------------------------------------------------------------------
            # tokenize
            doc_words = get_doc_index_list(doc_lower, vocab_dict, unk_dict)
            qry_words = get_doc_index_list(qry_lower, vocab_dict, unk_dict)
            ans_words = get_doc_index_list(ans_lower, vocab_dict, unk_dict)
            can_words = []
            for can in can_lower:
                can_words.append(get_doc_index_list(can, vocab_dict, unk_dict))

            doc_chars = get_char_index_list(doc_raw, vocab_c_dict, max_word_len)
            qry_chars = get_char_index_list(qry_raw, vocab_c_dict, max_word_len)

            #------------------------------------------------------------------------
            # other information
            annotations = data["annotations"]
            sample_id = data["id"]
            mentions = data["mentions"]
            corefs = data["coref_onehot"][:max_chains-1]

            one_sample = [doc_words, qry_words, ans_words, can_words, doc_chars, qry_chars]
            one_sample += [corefs, mentions, annotations, sample_id]

            ret.append(one_sample)
            
            if index > 30: break  # for test
    return ret


def get_graph(edges):
    dei, deo = edges
    dri, dro = np.copy(dei).astype("int32"), np.copy(deo).astype("int32")
    dri[:, :, 0] = 0
    dro[:, :, 0] = 0
    return dei, deo, dri, dro


def generate_batch_data(data, config):
    max_word_len = config['max_word_len']
    max_chains = config['max_chains']
    batch_size = config['batch_size']
    
    n_data = len(data)
    max_doc_len, max_qry_len, max_cands = 0, 0, 0

    batch_index = np.random.choice(n_data, batch_size, replace=True)

    for index in batch_index:
        doc_w, qry_w, ans, cand, doc_c, qry_c, corefs, mentions, annotations, fname = data[index]
        max_doc_len = max(max_doc_len, len(doc_w))
        max_qry_len = max(max_qry_len, len(qry_w))
        max_cands = max(max_cands, len(cand))
    
    # print(max_doc_len)
    # print(max_qry_len)
    # print(max_cands)

    #------------------------------------------------------------------------
    dw = np.zeros((batch_size, max_doc_len), dtype='int32') # document words
    m_dw = np.zeros((batch_size, max_doc_len), dtype='float32')  # document word mask
    qw = np.zeros((batch_size, max_qry_len), dtype='int32') # query words
    m_qw = np.zeros((batch_size, max_qry_len), dtype='float32')  # query word mask

    dc = np.zeros((batch_size, max_doc_len, max_word_len), dtype="int32")
    m_dc = np.zeros((batch_size, max_doc_len, max_word_len), dtype="float32")
    qc = np.zeros((batch_size, max_qry_len, max_word_len), dtype="int32")
    m_qc = np.zeros((batch_size, max_qry_len, max_word_len), dtype="float32")

    cd = np.zeros((batch_size, max_doc_len, max_cands), dtype='int32')   # candidate answers
    m_cd = np.zeros((batch_size, max_doc_len), dtype='float32') # candidate mask

    edges_in = np.zeros((batch_size, max_doc_len, max_chains), dtype="float32")
    edges_out = np.zeros((batch_size, max_doc_len, max_chains), dtype="float32")
    edges_in[:, :, 0] = 1.
    edges_out[:, :, 0] = 1.

    a = np.zeros((batch_size, ), dtype='int32')    # correct answer
    # fnames = ['']*batch_size
    # annots = []

    #------------------------------------------------------------------------
    for n in range(batch_size):
        doc_w, qry_w, ans, cand, doc_c, qry_c, corefs, mentions, annotations, fname = data[batch_index[n]]

        # document and query
        dw[n, :len(doc_w)] = doc_w
        qw[n, :len(qry_w)] = qry_w
        m_dw[n, :len(doc_w)] = 1
        m_qw[n, :len(qry_w)] = 1
        for t in range(len(doc_c)):
            dc[n, t, :len(doc_c[t])] = doc_c[t]
            m_dc[n, t, :len(doc_c[t])] = 1
        for t in range(len(qry_c)):
            qc[n, t, :len(qry_c[t])] = qry_c[t]
            m_qc[n, t, :len(qry_c[t])] = 1

        # search candidates in doc
        for it, cc in enumerate(cand):
            index = [ii for ii in range(len(doc_w)) if doc_w[ii] in cc]
            m_cd[n, index] = 1
            cd[n, index, it] = 1
            if ans == cc: 
                found_answer = True
                a[n] = it # answer

        # graph edges
        for ic, chain in enumerate(corefs):
            for item in chain:
                if item[2] != -1:
                    if mentions[item[2]][0] < max_doc_len:
                        edges_in[n, mentions[item[2]][0], ic+1] = 1.
                if item[0] != -1:
                    if mentions[item[0]][1]-1 < max_doc_len:
                        edges_out[n, mentions[item[0]][1]-1, ic+1] = 1.

        # annots.append(annotations)
        # fnames[n] = fname

    dei, deo, dri, dro = get_graph((edges_in, edges_out))
    ret = [dw, m_dw, qw, m_qw, dc, m_dc, qc, m_qc, cd, m_cd, a, dei, deo, dri, dro]
    return ret
        

def main():
    # load config file
    config = load_config(config_path)

    # build dict for token (vocab_dict) and char (vocab_c_dict)
    vocab_dict, vocab_c_dict = build_dict(vocab_path, vocab_char_path)

    # load pre-trained embedding
    # W_init: token index * token embeding
    # embed_dim: embedding dimension
    W_init, embed_dim = load_word2vec_embedding(word_embedding_path, vocab_dict)

    # print(W_init.shape)

    # generate train/valid examples
    train_data = generate_examples(train_path, vocab_dict, vocab_c_dict, config)
    valid_data = generate_examples(valid_path, vocab_dict, vocab_c_dict, config)

    #------------------------------------------------------------------------
    # training process begins
    hidden_size = 64
    # batch_size = 24  # for test
    batch_size = config['batch_size']
    K = 3

    # use to embed token embedding and char embedding
    # input_embed_model = EmbeddingLayer.InputEmbeddingLayer(W_init, config)

    coref_model = model.CorefQA(hidden_size, batch_size, K, W_init, config)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(coref_model.parameters(), lr=0.0005) # TODO: use hyper-params in paper

    iter_index = 0

    while True:
        # building batch data
        # batch_xxx_data is a list of batch data (len 15)
        # [dw, m_dw, qw, m_qw, dc, m_dc, qc, m_qc, cd, m_cd, a, dei, deo, dri, dro]
        batch_train_data = generate_batch_data(train_data, config)
        dw, m_dw, qw, m_qw, dc, m_dc, qc, m_qc, cd, m_cd, a, dei, deo, dri, dro = batch_train_data

        # k_layer = 0 # TODO to be changed
        # doc_emb, qry_emb = input_embed_model(dw, dc, qw, qc, k_layer, K)
        # print(doc_emb.shape)
        # print(qry_emb.shape)

        # zero the parameter gradients
        optimizer.zero_grad()

        # forward pass
        cand_probs = coref_model(batch_train_data) # B x Cmax

        # compute loss
        # Cmax = len(cd[0][0]) # max number of candidates in this batch
        # batch_answer_one_hot = [[1 if cand_id == a[sample_id] else 0 for cand_id in range(Cmax)] for sample_id in range(batch_size)]
        # answer = torch.tensor(batch_answer_one_hot).type(torch.LongTensor) # B x Cmax
        answer = torch.tensor(a).type(torch.LongTensor) # B x 1
        loss = criterion(cand_probs, answer)

        print(loss)
        
        # back-prop
        loss.backward()
        optimizer.step()

        # evaluation process
        

        # check stopping criteria
        iter_index += 1
        if iter_index > 100: break


if __name__ == "__main__":
    main()
