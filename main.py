'''Train CIFAR10 with PyTorch.'''
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import torch.backends.cudnn as cudnn

import torchvision
import torchvision.transforms as transforms

import os
import argparse
import csv
import time
import shutil

from models import *
from utils import progress_bar


parser = argparse.ArgumentParser(description='PyTorch CIFAR10 Training')
parser.add_argument('--arch', default="MobileNetV2", help='model architecture')
parser.add_argument('--lr', default=0.1, type=float, help='learning rate')
parser.add_argument('--resume', '-r', action='store_true', help='resume from checkpoint')
parser.add_argument('--save', default='./checkpoint', type=str, help='path to save model')
args = parser.parse_args()

device = 'cuda' if torch.cuda.is_available() else 'cpu'
best_acc = 0  # best test accuracy
start_epoch = 0  # start from epoch 0 or last checkpoint epoch

# Data
print('==> Preparing data..')
transform_train = transforms.Compose([
    transforms.RandomCrop(32, padding=4),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
])

transform_test = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
])

trainset = torchvision.datasets.CIFAR10(root='./data', train=True, download=True, transform=transform_train)
trainloader = torch.utils.data.DataLoader(trainset, batch_size=128, shuffle=True, num_workers=2)

testset = torchvision.datasets.CIFAR10(root='./data', train=False, download=True, transform=transform_test)
testloader = torch.utils.data.DataLoader(testset, batch_size=100, shuffle=False, num_workers=2)

classes = ('plane', 'car', 'bird', 'cat', 'deer', 'dog', 'frog', 'horse', 'ship', 'truck')

# Model
print('==> Building model..')
# net = VGG('VGG19')
# net = ResNet18()
# net = PreActResNet18()
# net = GoogLeNet()
# net = DenseNet121()
# net = ResNeXt29_2x64d()
# net = MobileNet()
# net = MobileNetV2()
# net = DPN92()
# net = ShuffleNetG2()
# net = SENet18()
# net = ShuffleNetV2(1)
# net = EfficientNetB0()
net = locals()[args.arch]()
net = net.to(device)
if device == 'cuda':
    net = torch.nn.DataParallel(net)
    cudnn.benchmark = True

if args.resume:
    # Load checkpoint.
    print('==> Resuming from checkpoint..')
    assert os.path.isdir(args.save), 'Error: no checkpoint directory found!'
    checkpoint = torch.load(os.path.join(args.save, 'checkpoint.pth'))
    net.load_state_dict(checkpoint['net'])
    best_acc = checkpoint['acc']
    start_epoch = checkpoint['epoch']

model_dir = args.save

criterion = nn.CrossEntropyLoss()
optimizer = optim.SGD(net.parameters(), lr=args.lr, momentum=0.9, weight_decay=5e-4)

# Training
def train(epoch):
    print('\nEpoch: %d' % epoch)
    net.train()
    train_loss = 0
    correct = 0
    total = 0
    batch_time_total = 0

    end = time.time()
    for batch_idx, (inputs, targets) in enumerate(trainloader):
        data_time = time.time() - end

        inputs, targets = inputs.to(device), targets.to(device)
        optimizer.zero_grad()
        outputs = net(inputs)
        loss = criterion(outputs, targets)
        loss.backward()
        optimizer.step()

        batch_time = time.time() - end

        train_loss += loss.item()
        _, predicted = outputs.max(1)
        total += targets.size(0)
        correct += predicted.eq(targets).sum().item()
        batch_time_total += batch_time

        end = time.time()

        progress_bar(batch_idx, len(trainloader), 'Loss: %.3f | Acc: %.3f%% (%d/%d)'
            % (train_loss/(batch_idx+1), 100.*correct/total, correct, total))

    return (train_loss/(batch_idx+1), 100.*correct/total, batch_time_total/(batch_idx+1))

def test(epoch):
    global best_acc
    net.eval()
    test_loss = 0
    correct = 0
    total = 0
    batch_time_total = 0
    with torch.no_grad():
        end = time.time()
        for batch_idx, (inputs, targets) in enumerate(testloader):
            data_time = time.time() - end 

            inputs, targets = inputs.to(device), targets.to(device)
            outputs = net(inputs)
            loss = criterion(outputs, targets)

            batch_time = time.time() - end

            test_loss += loss.item()
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()
            batch_time_total += batch_time

            end = time.time()

            progress_bar(batch_idx, len(testloader), 'Loss: %.3f | Acc: %.3f%% (%d/%d)'
                % (test_loss/(batch_idx+1), 100.*correct/total, correct, total))

    # Save checkpoint.
    acc = 100.*correct/total
    is_best = acc > best_acc
    best_acc = max(acc, best_acc)
    if is_best:
        try:
            torch.save(model, os.path.join(model_dir, "model.pth"))
        except: 
            print("WARNING: Unable to save model.pth")
        try:
            torch.save(model.state_dict(), os.path.join(model_dir, "weights.pth"))
        except: 
            print("WARNING: Unable to save weights.pth")

    save_checkpoint({
        'epoch': epoch + 1,
        'arch': args.arch,
        'state_dict': net.state_dict(),
        'best_acc1': best_acc,
        'optimizer' : optimizer,
        #'lr_scheduler' : lr_scheduler,
    }, is_best, model_dir)
    
    return (test_loss/(batch_idx+1), 100.*correct/total, batch_time_total/(batch_idx+1))

def save_checkpoint(state, is_best, dir_path, filename='checkpoint.pth.tar'):
    torch.save(state, os.path.join(dir_path, filename))
    if is_best:
        shutil.copyfile(os.path.join(dir_path, filename), os.path.join(dir_path, 'model_best.pth.tar'))
        
    if (state['epoch']-1)%10 == 0:
        shutil.copyfile(os.path.join(dir_path, filename), os.path.join(dir_path, 'checkpoint_' + str(state['epoch']-1) + '.pth.tar'))

# create log directory
if not os.path.exists(model_dir):
    os.makedirs(model_dir)

# create log file
with open(os.path.join(model_dir, "train_log.csv"), "w") as train_log_file:
    train_log_csv = csv.writer(train_log_file)
    train_log_csv.writerow(['epoch', 'train_loss', 'train_top1_acc', 'train_time', 'test_loss', 'test_top1_acc', 'test_time', 'cumulative_time'])

start_log_time = time.time()
for epoch in range(start_epoch, start_epoch+200):
    train_epoch_log = train(epoch)
    test_epoch_log = test(epoch)

    # append to log
    with open(os.path.join(model_dir, "train_log.csv"), "a") as train_log_file:
        train_log_csv = csv.writer(train_log_file)
        train_log_csv.writerow(((epoch,) + train_epoch_log + test_epoch_log + (time.time() - start_log_time,))) 
