from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# from caffe import params as P
import numpy as np


def _convert_conv(net, node, graph, err):
    weight_name = node.inputs[1]
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    node_name = node.name
    W = None
    if weight_name in node.input_tensors:
        W = node.input_tensors[weight_name]
    else:
        err.missing_initializer(node,
                                "Weight tensor: {} not found in the graph initializer".format(weight_name, ))
    bias_flag = False
    bias = None
    if len(node.inputs) > 2:
        bias = node.input_tensors[node.inputs[2]]
        bias_flag = True
    # net.params[node_name][0].data = W
    # if bias_flag:
    #     net.params[node_name][1].data = bias
    np.copyto(net.params[node_name][0].data, W, casting='same_kind')
    if bias_flag:
        np.copyto(net.params[node_name][1].data, bias, casting='same_kind')


def _convert_relu(net, node, graph, err):
    pass


def _convert_sigmoid(net, node, graph, err):
    pass


def _convert_BatchNorm(net, node, graph, err):
    scale = node.input_tensors[node.inputs[1]]
    bias = node.input_tensors[node.inputs[2]]
    mean = node.input_tensors[node.inputs[3]]
    var = node.input_tensors[node.inputs[4]]
    node_name = node.name
    np.copyto(net.params[node_name + '_bn'][0].data, mean, casting='same_kind')
    np.copyto(net.params[node_name + '_bn'][1].data, var, casting='same_kind')
    net.params[node_name + '_bn'][2].data[...] = 1.0
    np.copyto(net.params[node_name][0].data, scale, casting='same_kind')
    np.copyto(net.params[node_name][1].data, bias, casting='same_kind')
    # net.params[node_name+'_bn'][1].data = var
    # net.params[node_name][0].data = scale
    # net.params[node_name][1].data = bias


def _convert_Add(net, node, graph, err):
    pass


def _convert_Mul(net, node, graph, err):
    pass


def _convert_Reshape(net, node, graph, err):
    pass


def _convert_Flatten(net, node, graph, err):
    pass


def _convert_pool(net, node, graph, err):
    pass


def _convert_dropout(net, node, graph, err):
    pass


def _convert_gemm(net, node, graph, err):
    node_name = node.name
    weight_name = node.inputs[1]
    if weight_name in node.input_tensors:
        W = node.input_tensors[weight_name]
    else:
        err.missing_initializer(node,
                                "Weight tensor: {} not found in the graph initializer".format(weight_name, ))
    if ("broadcast" in node.attrs and node.attrs["broadcast"] != 1) or node.attrs["transB"] != 1:
        return err.unsupported_op_configuration(node, "Gemm is supported only for inner_product layer")
    b = None
    if len(node.inputs) > 2:
        b = node.input_tensors[node.inputs[2]]
    if len(W.shape) != 2 or (b is not None and len(b.shape) != 1):
        return err.unsupported_op_configuration(node, "Gemm is supported only for inner_product layer")
    if b is not None:
        if W.shape[0] != b.shape[0]:
            return err.unsupported_op_configuration(node, "Gemm is supported only for inner_product layer")
    net.params[node_name][0].data[...] = W
    net.params[node_name][1].data[...] = b


def _convert_upsample(net, node, graph, err):
    mode = node.attrs["mode"]
    node_name = node.name
    if mode == "nearest":
        caffe_params = net.params[node_name][0].data
        weights = np.ones(caffe_params.shape).astype("float32")
        np.copyto(net.params[node_name][0].data, weights, casting='same_kind')
        # net.params[node_name][0].data[]


def _convert_resize_opset11(net, node, graph, err):
    mode = node.attrs["mode"]
    node_name = node.name
    if mode == "nearest":
        caffe_params = net.params[node_name][0].data
        weights = np.ones(caffe_params.shape).astype("float32")
        np.copyto(net.params[node_name][0].data, weights, casting='same_kind')
        # net.params[node_name][0].data[]
    # else:
    #     if net.layer_dict[node_name].type == "Deconvolution":
    #         caffe_params = net.params[node_name][0].data
    #         filter_size = net.params[node_name][0].data.shape[2]
    #         bilinear_kernel = np.zeros([filter_size, filter_size], dtype=np.float32)
    #         scale_factor = (filter_size + 1) // 2
    #         scale_factor = (filter_size + 1) // 2
    #         if filter_size % 2 == 1:
    #             center = scale_factor - 1
    #         else:
    #             center = scale_factor - 0.5
    #         for x in range(filter_size):
    #             for y in range(filter_size):
    #                 bilinear_kernel[x, y] = (1 - abs(x - center) / scale_factor) * \
    #                                         (1 - abs(y - center) / scale_factor)
    #         weights = np.ones(caffe_params.shape).astype("float32")
    #         for i in range(caffe_params.shape[0]):
    #             weights[:, :, i, i] = bilinear_kernel
    #         np.copyto(net.params[node_name][0].data, weights, casting='same_kind')


def _convert_concat(net, node, graph, err):
    pass


def _convert_conv_slice(net, node, graph, err):
    pass


def _convert_conv_split_opset11(net, node, graph, err):
    pass


def _convert_conv_transpose(net, node, graph, err):
    weight_name = node.inputs[1]
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    node_name = node.name
    W = None
    if weight_name in node.input_tensors:
        W = node.input_tensors[weight_name]
    else:
        err.missing_initializer(node,
                                "Weight tensor: {} not found in the graph initializer".format(weight_name, ))
    bias_flag = False
    bias = None
    if len(node.inputs) > 2:
        bias = node.input_tensors[node.inputs[2]]
        bias_flag = True
    # net.params[node_name][0].data = W
    # if bias_flag:
    #     net.params[node_name][1].data = bias
    np.copyto(net.params[node_name][0].data, W, casting='same_kind')
    if bias_flag:
        np.copyto(net.params[node_name][1].data, bias, casting='same_kind')


_ONNX_NODE_REGISTRY = {
    "Conv": _convert_conv,
    "Relu": _convert_relu,
    "BatchNormalization": _convert_BatchNorm,
    "Add": _convert_Add,
    "Mul": _convert_Mul,
    "Reshape": _convert_Reshape,
    "MaxPool": _convert_pool,
    "AveragePool": _convert_pool,
    "GlobalAveragePool": _convert_pool,
    "Dropout": _convert_dropout,
    "Gemm": _convert_gemm,
    "Upsample": _convert_upsample,
    # "Resize": _convert_resize_opset11,
    "Resize": _convert_concat,
    "Concat": _convert_concat,
    "ConvTranspose": _convert_conv_transpose,
    "Sigmoid": _convert_sigmoid,
    "Flatten": _convert_Flatten,
    "Slice": _convert_conv_slice,
    "Split": _convert_conv_split_opset11,
}
