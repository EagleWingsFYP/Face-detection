from __future__ import print_function
import argparse
import os
import shutil
import time

import torch
import torch.nn as nn
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.optim
import torch.utils.data
import torchvision.transforms as transforms

import numpy as np

from object_detector.light_cnn import LightCNN_9Layers, LightCNN_29Layers, LightCNN_29Layers_v2
from load_imglist import ImageList

parser = argparse.ArgumentParser(description='PyTorch Light CNN Training')
parser.add_argument('--arch', '-a', metavar='ARCH', default='LightCNN')
parser.add_argument('--cuda', '-c', default=True)
parser.add_argument('-j', '--workers', default=4, type=int, metavar='N',
                    help='number of data loading workers (default: 4)')
parser.add_argument('--epochs', default=80, type=int, metavar='N',
                    help='number of total epochs to run')
parser.add_argument('--start-epoch', default=0, type=int, metavar='N',
                    help='manual epoch number (useful on restarts)')
parser.add_argument('-b', '--batch-size', default=128, type=int,
                    metavar='N', help='mini-batch size (default: 128)')
parser.add_argument('--lr', '--learning-rate', default=0.01, type=float,
                    metavar='LR', help='initial learning rate')
parser.add_argument('--momentum', default=0.9, type=float, metavar='M',
                    help='momentum')
parser.add_argument('--weight-decay', '--wd', default=1e-4, type=float,
                    metavar='W', help='weight decay (default: 1e-4)')
parser.add_argument('--print-freq', '-p', default=100, type=int,
                    metavar='N', help='print frequency (default: 100)')
parser.add_argument('--model', default='', type=str, metavar='Model',
                    help='model type: LightCNN-9, LightCNN-29, or LightCNN-29v2')
parser.add_argument('--resume', default='', type=str, metavar='PATH',
                    help='path to latest checkpoint (default: none)')
parser.add_argument('--root_path', default='', type=str, metavar='PATH',
                    help='path to root directory of images (default: none)')
parser.add_argument('--train_list', default='', type=str, metavar='PATH',
                    help='path to training list (default: none)')
parser.add_argument('--val_list', default='', type=str, metavar='PATH',
                    help='path to validation list (default: none)')
parser.add_argument('--save_path', default='', type=str, metavar='PATH',
                    help='path to save checkpoint (default: none)')
parser.add_argument('--num_classes', default=99891, type=int,
                    metavar='N', help='number of classes (default: 99891)')

parser.add_argument('--export', action='store_true',
                    help='Export model as a standalone TorchScript model for inference')
parser.add_argument('--export_path', default='standalone_model.pt', type=str,
                    help='Path to save the exported standalone model')

def main():
    global args
    args = parser.parse_args()

    if args.model == 'LightCNN-9':
        model = LightCNN_9Layers(num_classes=args.num_classes)
    elif args.model == 'LightCNN-29':
        model = LightCNN_29Layers(num_classes=args.num_classes)
    elif args.model == 'LightCNN-29v2':
        model = LightCNN_29Layers_v2(num_classes=args.num_classes)
    else:
        print('Error: Invalid model type. Please choose from LightCNN-9, LightCNN-29, or LightCNN-29v2\n')
        return

    if args.cuda and torch.cuda.is_available():
        model = torch.nn.DataParallel(model).cuda()
    else:
        print("Running on CPU because CUDA is not available or not enabled.")

    print(model)

    params = []
    for name, value in model.named_parameters():
        if 'bias' in name:
            if 'fc2' in name:
                params += [{'params': value, 'lr': 20 * args.lr, 'weight_decay': 0}]
            else:
                params += [{'params': value, 'lr': 2 * args.lr, 'weight_decay': 0}]
        else:
            if 'fc2' in name:
                params += [{'params': value, 'lr': 10 * args.lr}]
            else:
                params += [{'params': value, 'lr': 1 * args.lr}]

    optimizer = torch.optim.SGD(params, args.lr,
                                momentum=args.momentum,
                                weight_decay=args.weight_decay)

    if args.resume:
        if os.path.isfile(args.resume):
            print("=> loading checkpoint '{}'".format(args.resume))
            checkpoint = torch.load(args.resume)
            args.start_epoch = checkpoint['epoch']
            model.load_state_dict(checkpoint['state_dict'])
            print("=> loaded checkpoint '{}' (epoch {})"
                  .format(args.resume, checkpoint['epoch']))
        else:
            print("=> no checkpoint found at '{}'".format(args.resume))

    cudnn.benchmark = True

    train_loader = torch.utils.data.DataLoader(
        ImageList(root=args.root_path, fileList=args.train_list, 
                  transform=transforms.Compose([ 
                      transforms.RandomCrop(128),
                      transforms.RandomHorizontalFlip(), 
                      transforms.ToTensor(),
                  ])),
        batch_size=args.batch_size, shuffle=True,
        num_workers=args.workers, pin_memory=True)

    val_loader = torch.utils.data.DataLoader(
        ImageList(root=args.root_path, fileList=args.val_list, 
                  transform=transforms.Compose([ 
                      transforms.CenterCrop(128),
                      transforms.ToTensor(),
                  ])),
        batch_size=args.batch_size, shuffle=False,
        num_workers=args.workers, pin_memory=True)   

    criterion = nn.CrossEntropyLoss()
    if args.cuda:
        criterion = criterion.cuda()

    validate(val_loader, model, criterion)    

    for epoch in range(args.start_epoch, args.epochs):
        adjust_learning_rate(optimizer, epoch)

        train(train_loader, model, criterion, optimizer, epoch)

        prec1 = validate(val_loader, model, criterion)

        save_name = os.path.join(args.save_path, 'lightCNN_' + str(epoch+1) + '_checkpoint.pth.tar')
        save_checkpoint({
            'epoch': epoch + 1,
            'arch': args.arch,
            'state_dict': model.state_dict(),
            'prec1': prec1,
        }, save_name)

    if args.export:
        export_standalone_model(model, args.export_path)
        print("Standalone model exported to {}".format(args.export_path))


def train(train_loader, model, criterion, optimizer, epoch):
    batch_time = AverageMeter()
    data_time  = AverageMeter()
    losses     = AverageMeter()
    top1       = AverageMeter()
    top5       = AverageMeter()

    model.train()

    end = time.time()
    for i, (input, target) in enumerate(train_loader):
        data_time.update(time.time() - end)

        input  = input.cuda()
        target = target.cuda()
        output, _ = model(input)
        loss = criterion(output, target)

        prec1, prec5 = accuracy(output.data, target, topk=(1, 5))
        losses.update(loss.item(), input.size(0))
        top1.update(prec1[0], input.size(0))
        top5.update(prec5[0], input.size(0))

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        batch_time.update(time.time() - end)
        end = time.time()

        if i % args.print_freq == 0:
            print('Epoch: [{0}][{1}/{2}]\t'
                  'Time {batch_time.val:.3f} ({batch_time.avg:.3f})\t'
                  'Data {data_time.val:.3f} ({data_time.avg:.3f})\t'
                  'Loss {loss.val:.4f} ({loss.avg:.4f})\t'
                  'Prec@1 {top1.val:.3f} ({top1.avg:.3f})\t'
                  'Prec@5 {top5.val:.3f} ({top5.avg:.3f})'.format(
                   epoch, i, len(train_loader), batch_time=batch_time,
                   data_time=data_time, loss=losses, top1=top1, top5=top5))


def validate(val_loader, model, criterion):
    batch_time = AverageMeter()
    losses     = AverageMeter()
    top1       = AverageMeter()
    top5       = AverageMeter()

    model.eval()

    end = time.time()
    with torch.no_grad():
        for i, (input, target) in enumerate(val_loader):
            input  = input.cuda()
            target = target.cuda()
            output, _ = model(input)
            loss = criterion(output, target)

            prec1, prec5 = accuracy(output.data, target, topk=(1, 5))
            losses.update(loss.item(), input.size(0))
            top1.update(prec1[0], input.size(0))
            top5.update(prec5[0], input.size(0))

            batch_time.update(time.time() - end)
            end = time.time()

    print('\nTest set: Average loss: {:.4f}, Accuracy: ({:.3f}%)\n'.format(losses.avg, top1.avg))
    return top1.avg


def save_checkpoint(state, filename):
    torch.save(state, filename)


class AverageMeter(object):
    """Computes and stores the average and current value."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.val   = 0
        self.avg   = 0
        self.sum   = 0
        self.count = 0

    def update(self, val, n=1):
        self.val   = val
        self.sum   += val * n
        self.count += n
        self.avg   = self.sum / self.count


def adjust_learning_rate(optimizer, epoch):
    scale = 0.457305051927326
    step  = 10
    lr = args.lr * (scale ** (epoch // step))
    print('Current lr: {}'.format(lr))
    if (epoch != 0) and (epoch % step == 0):
        print('Adjusting learning rate')
        for param_group in optimizer.param_groups:
            param_group['lr'] = param_group['lr'] * scale


def accuracy(output, target, topk=(1,)):
    """Computes the precision@k for the specified values of k."""
    maxk = max(topk)
    batch_size = target.size(0)

    _, pred = output.topk(maxk, 1, True, True)
    pred = pred.t()
    correct = pred.eq(target.view(1, -1).expand_as(pred))

    res = []
    for k in topk:
        correct_k = correct[:k].reshape(-1).float().sum(0)
        res.append(correct_k.mul_(100.0 / batch_size))
    return res


def export_standalone_model(model, export_path):
    """
    Export the trained model as a TorchScript file.
    This allows the model to be loaded for inference without the training code.
    """
    model.eval()
    device = next(model.parameters()).device
    example_input = torch.randn(1, 1, 128, 128).to(device)
    traced_model = torch.jit.trace(model, example_input)
    traced_model.save(export_path)

if __name__ == '__main__':
    main()
