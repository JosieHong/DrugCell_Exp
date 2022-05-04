###
 # @Date: 2022-04-28 13:01:14
 # @LastEditors: yuhhong
 # @LastEditTime: 2022-05-03 20:37:58
### 
#!/bin/bash
inputdir="../data/"
gene2idfile=$inputdir"gene2ind.txt"
cell2idfile=$inputdir"cell2ind.txt"
drug2idfile=$inputdir"drug2ind.txt"
traindatafile=$inputdir"drugcell_train.txt"
valdatafile=$inputdir"drugcell_val.txt"
ontfile=$inputdir"drugcell_ont.txt"

mutationfile=$inputdir"cell2mutation.txt"
drugfile=$inputdir"drug2fingerprint.txt"

cudaid=0

modeldir="./ours_train_graph/Model_sample"
mkdir $modeldir

source activate pytorch3drugcell

# python -u ../code/train_drugcell.py -onto $ontfile -gene2id $gene2idfile -drug2id $drug2idfile -cell2id $cell2idfile -train $traindatafile -test $valdatafile -model $modeldir -cuda $cudaid -genotype $mutationfile -fingerprint $drugfile -genotype_hiddens 6 -drug_hiddens '100,50,6' -final_hiddens 6 -epoch 100 -batchsize 5000 > train_sample.log
python -u ../code/train_our_drugcell_graph.py -onto $ontfile -gene2id $gene2idfile -drug2id $drug2idfile -cell2id $cell2idfile -train $traindatafile -test $valdatafile -model $modeldir -cuda $cudaid -genotype $mutationfile -fingerprint $drugfile -genotype_hiddens 6 -drug_hiddens '8,16,32' -final_hiddens 6 -epoch 100 -batchsize 640 -lr 0.0001
