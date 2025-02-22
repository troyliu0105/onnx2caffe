from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import math

from caffe import params as P

from MyCaffe import Function as myf


def _compare(a, b, encoding="utf8"):  # type: (Text, Text, Text) -> bool
    if isinstance(a, bytes):
        a = a.decode(encoding)
    if isinstance(b, bytes):
        b = b.decode(encoding)
    return a == b


def make_input(input):
    name = input[0]
    output = input[0]
    output = [output]
    shape = input[2]
    shape = list(shape)
    input_layer = myf("Input", name, [], output, input_param=dict(shape=dict(dim=shape)))
    return input_layer


def _convert_conv(node, graph, err):
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
    is_deconv = False
    if node.op_type.endswith("Transpose"):
        is_deconv = True
    bias_flag = False
    bias = None
    if len(node.inputs) > 2:
        bias = node.input_tensors[node.inputs[2]]
        bias_flag = True
    dilations = node.attrs.get("dilations", [1, 1])
    # groups = 1
    groups = node.attrs.get("group", 1)
    kernel_shape = node.attrs["kernel_shape"]
    pads = node.attrs.get("pads", [0, 0, 0, 0])
    strides = node.attrs["strides"]

    layer = myf("Convolution", node_name, [input_name], [output_name],
                kernel_h=kernel_shape[0], kernel_w=kernel_shape[1],
                stride_h=strides[0], stride_w=strides[1], group=groups,
                pad_h=pads[0], pad_w=pads[1],
                num_output=W.shape[0], dilation=dilations[0], bias_term=bias_flag)

    graph.channel_dims[output_name] = W.shape[0]
    return layer


def _convert_relu(node, graph, err):
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    name = str(node.name)

    if input_name == output_name:
        inplace = True
    else:
        inplace = False

    layer = myf("ReLU", name, [input_name], [output_name], in_place=inplace)
    # l_top_relu1 = L.ReLU(l_bottom, name=name, in_place=True)

    graph.channel_dims[output_name] = graph.channel_dims[input_name]

    return layer


def _convert_sigmoid(node, graph, err):
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    name = str(node.name)

    if input_name == output_name:
        inplace = True
    else:
        inplace = False

    layer = myf("Sigmoid", name, [input_name], [output_name], in_place=inplace)
    # l_top_relu1 = L.ReLU(l_bottom, name=name, in_place=True)

    graph.channel_dims[output_name] = graph.channel_dims[input_name]

    return layer


def _convert_BatchNorm(node, graph, err):
    epsilon = node.attrs.get("epsilon", 1e-5)
    scale = node.input_tensors[node.inputs[1]]
    bias = node.input_tensors[node.inputs[2]]
    mean = node.input_tensors[node.inputs[3]]
    var = node.input_tensors[node.inputs[4]]
    node_name = node.name

    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])

    if input_name == output_name:
        inplace = True
    else:
        inplace = False

    bn_layer = myf("BatchNorm", node_name + "_bn", [input_name], [output_name], eps=epsilon, use_global_stats=True,
                   in_place=inplace)
    scale_layer = myf("Scale", node_name, [output_name], [output_name], in_place=True, bias_term=True)

    graph.channel_dims[output_name] = graph.channel_dims[input_name]

    return bn_layer, scale_layer


def _convert_Add(node, graph, err):
    input_name_list = [str(i) for i in node.inputs]
    output_name = str(node.outputs[0])
    node_name = node.name

    max_dim = 0
    for name in input_name_list:
        if graph.channel_dims[name] > max_dim:
            max_dim = graph.channel_dims[name]

    if 'broadcast' in node.attrs:
        if node.attrs['broadcast'] == 1:
            input_node_number = len(input_name_list)
            if input_node_number != 2:
                return err.unsupported_op_configuration(node, "Broadcast Add must has 2 input, not {}".format(
                    input_node_number))
            axis = node.attrs['axis']
            flat_layer = myf("Flatten", node_name + '_flat', [input_name_list[1]], [output_name + '_flat'])
            layer = myf("Bias", node_name, [input_name_list[0], output_name + '_flat'], [output_name], axis=axis)
            # layer = myf("Bias", node_name, input_name_list, [output_name], bias_term = False, axis = axis)
            graph.channel_dims[output_name] = graph.channel_dims[input_name_list[0]]
            return flat_layer, layer

    layer = myf("Eltwise", node_name, input_name_list, [output_name], operation=P.Eltwise.SUM)
    graph.channel_dims[output_name] = graph.channel_dims[input_name_list[0]]
    return layer


def _convert_Mul(node, graph, err):
    input_name_list = [str(i) for i in node.inputs]
    output_name = str(node.outputs[0])
    node_name = node.name

    # max_dim = 0
    # for name in input_name_list:
    #     if graph.channel_dims[name]>max_dim:
    #         max_dim = graph.channel_dims[name]

    if 'broadcast' in node.attrs:
        if node.attrs['broadcast'] == 1:
            input_node_number = len(input_name_list)
            if input_node_number != 2:
                return err.unsupported_op_configuration(node, "Broadcast Mul must has 2 input, not {}".format(
                    input_node_number))
            axis = node.attrs['axis']
            flat_layer = myf("Flatten", node_name + '_flat', [input_name_list[1]], [output_name + '_flat'])
            layer = myf("Scale", node_name, [input_name_list[0], output_name + '_flat'], [output_name], bias_term=False,
                        axis=axis)
            graph.channel_dims[output_name] = graph.channel_dims[input_name_list[0]]
            return flat_layer, layer

    layer = myf("Eltwise", node_name, input_name_list, [output_name], operation=P.Eltwise.PROD)
    graph.channel_dims[output_name] = graph.channel_dims[input_name_list[0]]
    return layer


def _convert_Reshape(node, graph, err):
    node_name = node.name
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    if len(node.inputs) == 1:
        shape = tuple(node.attrs.get('shape', ()))
    else:
        shape = tuple(node.input_tensors[node.inputs[1]])
    # if shape == ():

    if input_name == output_name:
        inplace = True
    else:
        inplace = False
    if len(shape) == 2:
        layer = myf("Flatten", node_name, [input_name], [output_name], in_place=inplace)
        graph.channel_dims[output_name] = shape[1]
        return layer
    elif len(shape) == 4:
        graph.channel_dims[output_name] = shape[1]
        layer = myf("Reshape", node_name, [input_name], [output_name], reshape_param=dict(shape=dict(dim=list(shape))))
        return layer
    else:
        return err.unsupported_op_configuration(node, "Reshape dimention number shall be 2 or 4")


def _convert_Flatten(node, graph, err):
    node_name = node.name
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    # shape = tuple(node.attrs.get('shape', ()))
    if input_name == output_name:
        inplace = True
    else:
        inplace = False
    layer = myf("Flatten", node_name, [input_name], [output_name], in_place=inplace)
    # graph.channel_dims[output_name] = shape[1]
    return layer


def _convert_pool(node, graph, err):
    node_name = node.name
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    if node.op_type.endswith("MaxPool"):
        pool_type = P.Pooling.MAX
    elif node.op_type.endswith("AveragePool"):
        pool_type = P.Pooling.AVE
    else:
        return err.unsupported_op_configuration(node, "Unsupported pool type")

    global_pooling = int(node.op_type.startswith("Global"))
    if global_pooling == 0:
        kernel_shape = node.attrs["kernel_shape"]
        strides = node.attrs.get('strides', [1, 1])
        pads = node.attrs.get('pads', [0, 0, 0, 0])
        pooling_param = dict(pool=pool_type,
                             kernel_h=kernel_shape[0],
                             kernel_w=kernel_shape[1],
                             stride_h=strides[0],
                             stride_w=strides[1],
                             pad_h=pads[0],
                             pad_w=pads[1],
                             global_pooling=global_pooling)
    else:
        pooling_param = dict(pool=pool_type,
                             global_pooling=global_pooling)

    layer = myf("Pooling", node_name, [input_name], [output_name], pooling_param=pooling_param)
    graph.channel_dims[output_name] = graph.channel_dims[input_name]
    return layer


def _convert_dropout(node, graph, err):
    node_name = node.name
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    ratio = node.attrs.get('ratio', 0.5)
    layer = myf("Dropout", node_name, [input_name], [output_name], dropout_ratio=ratio)
    graph.channel_dims[output_name] = graph.channel_dims[input_name]
    return layer


def _convert_gemm(node, graph, err):
    node_name = node.name
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    weight_name = node.inputs[1]
    if weight_name in node.input_tensors:
        W = node.input_tensors[weight_name]
    else:
        err.missing_initializer(node,
                                "Weight tensor: {} not found in the graph initializer".format(weight_name, ))
        return

    if ("broadcast" in node.attrs and node.attrs["broadcast"] != 1) or node.attrs["transB"] != 1:
        return err.unsupported_op_configuration(node, "Gemm is supported only for inner_product layer")

    b = None
    bias_flag = False
    if len(node.inputs) > 2:
        b = node.input_tensors[node.inputs[2]]

    if len(W.shape) != 2 or (b is not None and len(b.shape) != 1):
        return err.unsupported_op_configuration(node, "Gemm is supported only for inner_product layer")
    if b is not None:
        bias_flag = True
        if W.shape[0] != b.shape[0]:
            return err.unsupported_op_configuration(node,
                                                    "Gemm is supported only for inner_product layer")

    layer = myf("InnerProduct", node_name, [input_name], [output_name], num_output=W.shape[0], bias_term=bias_flag)
    graph.channel_dims[output_name] = W.shape[0]

    return layer


def _convert_upsample(node, graph, err):
    try:
        factor = int(node.attrs["height_scale"])
    except KeyError:
        factor = int(node.input_tensors[node.inputs[-1]][2:].mean())
    node_name = node.name
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    # input_shape = graph.shape_dict[input_name]
    # channels = input_shape[1]
    channels = graph.channel_dims[input_name]
    pad = int(math.ceil((factor - 1) / 2.))
    # layer = myf("Deconvolution", node_name, [input_name], [output_name],
    #             kernel_size=2 * factor - factor % 2,
    #             stride=factor, group=channels,
    #             pad = pad, num_output=channels, bias_term = False)
    mode = node.attrs["mode"]
    # https://github.com/pytorch/pytorch/issues/6900
    if mode == "bilinear":
        layer = myf("Deconvolution", node_name, [input_name], [output_name],
                    convolution_param=dict(
                        num_output=channels,
                        kernel_size=2 * factor - factor % 2,
                        stride=factor,
                        pad=pad,
                        group=channels,
                        bias_term=False,
                        weight_filler=dict(type="bilinear_upsampling")
                    ))
    else:
        layer = myf("Deconvolution", node_name, [input_name], [output_name],
                    convolution_param=dict(
                        num_output=channels,
                        kernel_size=factor,
                        stride=factor,
                        group=channels,
                        bias_term=False,
                    ))

    graph.channel_dims[output_name] = graph.channel_dims[input_name]
    return layer


def _convert_resize_to_upsample_opset11(node, graph, err):
    factor = int(node.input_tensors[node.inputs[-1]][2:].mean())
    node_name = node.name
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    # input_shape = graph.shape_dict[input_name]
    # channels = input_shape[1]
    channels = graph.channel_dims[input_name]
    pad = int(math.ceil((factor - 1) / 2.))
    # mode = "bilinear"
    node.attrs["mode"] = "nearest"
    mode = node.attrs["mode"]
    layer = myf("Upsample", node_name, [input_name], [output_name],
                upsample_param=dict(
                    scale=factor
                ))
    graph.channel_dims[output_name] = graph.channel_dims[input_name]
    return layer

def _convert_resize_opset11(node, graph, err):
    factor = int(node.input_tensors[node.inputs[-1]][2:].mean())
    node_name = node.name
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    # input_shape = graph.shape_dict[input_name]
    # channels = input_shape[1]
    channels = graph.channel_dims[input_name]
    pad = int(math.ceil((factor - 1) / 2.))
    # mode = "bilinear"
    node.attrs["mode"] = "nearest"
    mode = node.attrs["mode"]

    # https://github.com/pytorch/pytorch/issues/6900
    if mode == "bilinear":
        if factor == 1:
            layer = myf("Convolution", node_name, [input_name], [output_name],
                        convolution_param=dict(
                            num_output=channels,
                            kernel_size=2 * factor - factor % 2,
                            stride=factor,
                            pad=pad,
                            group=channels,
                            bias_term=False,
                            # weight_filler=dict(type="bilinear_upsampling")
                            weight_filler=dict(type="bilinear")
                        ))
        else:
            layer = myf("Deconvolution", node_name, [input_name], [output_name],
                        convolution_param=dict(
                            num_output=channels,
                            kernel_size=2 * factor - factor % 2,
                            stride=factor,
                            pad=pad,
                            group=channels,
                            bias_term=False,
                            # weight_filler=dict(type="bilinear_upsampling")
                            weight_filler=dict(type="bilinear")
                        ))
    else:
        if factor == 1:
            layer = myf("Convolution", node_name, [input_name], [output_name],
                        convolution_param=dict(
                            num_output=channels,
                            kernel_size=2 * factor - factor % 2,
                            stride=factor,
                            pad=pad,
                            group=channels,
                            bias_term=False,
                            # weight_filler=dict(type="bilinear_upsampling")
                            weight_filler=dict(type="bilinear")
                        ))
        else:
            layer = myf("Deconvolution", node_name, [input_name], [output_name],
                        convolution_param=dict(
                            num_output=channels,
                            kernel_size=factor,
                            stride=factor,
                            group=channels,
                            bias_term=False,
                        ))

    graph.channel_dims[output_name] = graph.channel_dims[input_name]
    return layer


def _convert_concat(node, graph, err):
    node_name = node.name
    input_name_list = [str(i) for i in node.inputs]
    output_name = str(node.outputs[0])
    axis = node.attrs.get("axis", 1)

    layer = myf('Concat', node_name, input_name_list, [output_name], axis=axis)
    if axis == 1:
        dim = 0
        for name in input_name_list:
            dim += graph.channel_dims[name]
        graph.channel_dims[output_name] = dim
    else:
        graph.channel_dims[output_name] = graph.channel_dims[input_name_list[0]]

    return layer


def _convert_conv_transpose(node, graph, err):
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    node_name = node.name
    weight_name = node.inputs[1]
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
    dilations = node.attrs.get("dilations", [1, 1])
    # groups = 1
    groups = node.attrs.get("group", 1)
    kernel_shape = node.attrs["kernel_shape"]
    pads = node.attrs.get("pads", [0, 0, 0, 0])
    strides = node.attrs["strides"]

    layer = myf('Deconvolution', node_name, [input_name], [output_name],
                convolution_param=dict(
                    num_output=W.shape[1],
                    kernel_h=kernel_shape[0], kernel_w=kernel_shape[1],
                    stride_h=strides[0], stride_w=strides[1],
                    group=groups,
                    pad_h=pads[0], pad_w=pads[1],
                    bias_term=bias_flag,
                ))

    graph.channel_dims[output_name] = W.shape[1]
    return layer

    # l_top = L.Deconvolution(
    #     l_bottom,
    #     name=name,
    #     convolution_param=dict(
    #         num_output=W.shape[1],
    #         kernel_h=kernel_h,
    #         kernel_w=kernel_w,
    #         stride_h=stride_h,
    #         stride_w=stride_w,
    #         pad_h=pad_h,
    #         pad_w=pad_w,
    #         group=groups,
    #         bias_term=bias_term))

def _convert_conv_slice(node, graph, err):
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    node_name = node.name
    axes = node.attrs.get('axes', [])

    channels = graph.channel_dims[input_name]

    if len(axes) != 1:
        return err.unsupported_op_configuration(node, "Only single axis Slice is supported now")

    starts = node.attrs['starts']
    ends = node.attrs['ends']
    axes = node.attrs.get('axes', [])

    start = starts[0]
    end = ends[0]
    valid_pts = []
    for pt in [start, end]:
        if pt is not None and pt != 0 and pt != channels:
            valid_pts.append(pt)

    if start == 0:
        output_name_list = [output_name, str(output_name) + "slice_another"]
    else:
        output_name_list = [str(output_name) + "slice_another", output_name]

    if len(axes) == 0: axes = range(len(starts))
    if len(axes) == 1:
        if axes[0] == 0:
            axis = 'channel'
        elif axes[0] == 1:
            axis = 'height'
        elif axes[0] == 2:
            axis = 'width'
        else:
            return err.unsupported_op_configuration(node, "Slice is supported only along H, W or C dimensions")
    else:
        return err.unsupported_op_configuration(node,
                                                "Slice is supported only along one axis for 3D or 4D Tensors")

    layer = myf('Slice', node_name, [input_name], output_name_list, slice_dim=axes[0], slice_point=valid_pts)
    graph.channel_dims[output_name_list[0]] = valid_pts[0]
    graph.channel_dims[output_name_list[-1]] = channels - valid_pts[-1]
    return layer


def _convert_conv_slice_opset11(node, graph, err):
    input_name = str(node.inputs[0])
    output_name = str(node.outputs[0])
    node_name = node.name
    # axes = node.attrs.get('axes', [])
    names = node.inputs[1:]
    starts_name = names[0]
    ends_name = names[1]
    axes_name = names[2]
    steps_name = names[3]

    channels = graph.channel_dims[input_name]

    starts = node.input_tensors[starts_name]
    ends = node.input_tensors[ends_name]
    axes = node.input_tensors[axes_name]

    if len(axes) != 1:
        return err.unsupported_op_configuration(node, "Only single axis Slice is supported now")

    start = starts[0]
    end = ends[0]
    valid_pts = []
    for pt in [start, end]:
        if pt is not None and pt != 0 and pt != channels:
            valid_pts.append(pt)

    if start == 0:
        output_name_list = [output_name, str(output_name) + "slice_another"]
        output_channels = {
            output_name_list[0]: valid_pts[0],
            output_name_list[1]: channels - valid_pts[0]
        }
    elif len(valid_pts) == 1:
        output_name_list = [str(output_name) + "slice_another", output_name]
        output_channels = {
            output_name_list[0]: valid_pts[0],
            output_name_list[1]: channels - valid_pts[0]
        }
    elif len(valid_pts) == 2:
        output_name_list = [str(output_name) + "slice_another", output_name, str(output_name) + "slice_another_end"]
        output_channels = {
            output_name_list[0]: valid_pts[0],
            output_name_list[1]: valid_pts[1] - valid_pts[0],
            output_name_list[2]: channels - valid_pts[1]
        }
        # output_name_list = [output_name, str(output_name) + "slice_another_end"]

    if len(axes) == 0:
        axes = range(len(starts))
    if len(axes) == 1:
        if axes[0] == 0:
            axes = 'batch'
        elif axes[0] == 1:
            axis = 'channel'
        elif axes[0] == 2:
            axis = 'height'
        elif axes[0] == 3:
            axis = 'width'
        else:
            return err.unsupported_op_configuration(node, "Slice is supported only along H, W or C dimensions")
    else:
        return err.unsupported_op_configuration(node,
                                                "Slice is supported only along one axis for 3D or 4D Tensors")

    layer = myf('Slice', node_name, [input_name], output_name_list, slice_dim=axes[0], slice_point=valid_pts)
    # graph.channel_dims[output_name_list[0]] = valid_pts[0] if len(valid_pts) == 1 else valid_pts[1] - valid_pts[0]
    # graph.channel_dims[output_name_list[-1]] = channels - valid_pts[-1]
    for k, v in output_channels.items():
        graph.channel_dims[k] = v
    return layer


def _convert_conv_split_opset11(node, graph, err):
    node_name = node.name
    input_name = node.inputs[0]
    output_name_list = node.outputs
    attrs = node.attrs
    axis = attrs["axis"]
    splits = attrs["split"]
    valid_pts = [a * b for a, b in zip(splits, list(range(1, len(splits) + 1)))][:-1]
    layer = myf('Slice', node_name, [input_name], output_name_list, slice_dim=axis, slice_point=valid_pts)
    for output_name, output_channels in zip(output_name_list, splits):
        graph.channel_dims[output_name] = output_channels
    return layer


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
    # "Upsample": _convert_upsample,
    "Upsample": _convert_resize_to_upsample_opset11,
    # "Resize": _convert_resize_opset11,
    "Resize": _convert_resize_to_upsample_opset11,
    "Concat": _convert_concat,
    "ConvTranspose": _convert_conv_transpose,
    "Sigmoid": _convert_sigmoid,
    "Flatten": _convert_Flatten,
    "Slice": _convert_conv_slice,
    # "Slice": _convert_conv_slice_opset11,
    "Split": _convert_conv_split_opset11,
}
