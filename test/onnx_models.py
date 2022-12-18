from itertools import zip_longest

import onnx
import onnx.shape_inference
import onnx.numpy_helper
import numpy as np


def shapes_broadcastable(shape_a: tuple[int, ...], shape_b: tuple[int, ...]):
    return all((m == n) or (m == 1) or (n == 1) for m, n in zip(shape_a[::-1], shape_b[::-1]))


def gemm(k: int, m: int, n: int, random_seed: int):
    rng = np.random.default_rng(random_seed)

    input_name, output_name = "input", "output"
    input = onnx.helper.make_tensor_value_info(input_name, onnx.TensorProto.FLOAT, [k, m])
    output = onnx.helper.make_tensor_value_info(output_name, onnx.TensorProto.FLOAT, [k, n])

    weight_data = rng.normal(size=(m, n)).astype(np.float32)
    bias_data = rng.normal(size=n).astype(np.float32)

    weight_name = "weight"
    weight = onnx.numpy_helper.from_array(weight_data, weight_name)

    bias_name = "bias"
    bias = onnx.numpy_helper.from_array(bias_data, bias_name)

    node = onnx.helper.make_node(
        name="Gemm",
        op_type="Gemm",
        inputs=[input_name, weight_name, bias_name],
        outputs=[output_name],
    )

    graph_def = onnx.helper.make_graph(
        nodes=[node],
        name="Gemm",
        inputs=[input],
        outputs=[output],
        initializer=[weight, bias],
    )

    onnx_model = onnx.helper.make_model(graph_def, producer_name="tinyquant-test")
    onnx_model.opset_import[0].version = 13

    onnx_model = onnx.shape_inference.infer_shapes(onnx_model)

    onnx.checker.check_model(onnx_model)

    return onnx_model


def matmul(a_shape: tuple[int, ...], b_shape: tuple[int, ...]):
    assert len(a_shape) > 2, "Input shape a must habe at least 2 dimensions"
    assert len(b_shape) > 2, "Input shape b must habe at least 2 dimensions"
    assert a_shape[-1] == b_shape[-2], (f"shapes a_shape={a_shape}, b_shape={b_shape} have no matching last and "
                                        f"second last dimension.")
    assert shapes_broadcastable(a_shape[:-2], b_shape[:-2]), (
        f"shapes a_shape[:-2]={a_shape[:-2]}, b_shape[:-2]={b_shape[:-2]} are not broadcastable.")

    out_shape = (tuple(max(a_d, b_d) for a_d, b_d in zip_longest(a_shape[:-2], b_shape[:-2], fillvalue=1))
                 + a_shape[-2:-1] + b_shape[-1:])

    input_a_name, input_b_name, output_name = "input_a", "input_b", "output"
    input_a = onnx.helper.make_tensor_value_info(input_a_name, onnx.TensorProto.FLOAT, list(a_shape))
    input_b = onnx.helper.make_tensor_value_info(input_b_name, onnx.TensorProto.FLOAT, list(b_shape))
    output = onnx.helper.make_tensor_value_info(output_name, onnx.TensorProto.FLOAT, list(out_shape))

    node = onnx.helper.make_node(
        name="MatMul",
        op_type="MatMul",
        inputs=[input_a_name, input_b_name],
        outputs=[output_name],
    )

    graph_def = onnx.helper.make_graph(
        nodes=[node],
        name="MatMul",
        inputs=[input_a, input_b],
        outputs=[output],
    )

    onnx_model = onnx.helper.make_model(graph_def, producer_name="tinyquant-test")
    onnx_model.opset_import[0].version = 13

    onnx_model = onnx.shape_inference.infer_shapes(onnx_model)

    onnx.checker.check_model(onnx_model)

    onnx.save(onnx_model, "matmul.onnx")

    return onnx_model


def conv(b: int,
         c: int,
         inp_shape: (int, int),
         out_c: int,
         kernel_shape: (int, int),
         pads: (int, int, int, int),
         strides: (int, int),
         random_seed: int):
    rng = np.random.default_rng(random_seed)

    out_width = (inp_shape[0] - kernel_shape[0] + pads[0] + pads[2]) // strides[0] + 1
    out_height = (inp_shape[1] - kernel_shape[1] + pads[1] + pads[3]) // strides[1] + 1

    input_name, output_name = "input", "output"
    input = onnx.helper.make_tensor_value_info(input_name, onnx.TensorProto.FLOAT, [b, c, *inp_shape])
    output = onnx.helper.make_tensor_value_info(output_name, onnx.TensorProto.FLOAT,
                                                [b, out_c, out_width, out_height])

    weight_data = rng.normal(size=(out_c, c, *kernel_shape)).astype(np.float32)
    bias_data = rng.normal(size=out_c).astype(np.float32)

    weight_name = "weight"
    weight = onnx.numpy_helper.from_array(weight_data, weight_name)

    bias_name = "bias"
    bias = onnx.numpy_helper.from_array(bias_data, bias_name)

    node = onnx.helper.make_node(
        name="Conv",
        op_type="Conv",
        inputs=[input_name, weight_name, bias_name],
        outputs=[output_name],
        kernel_shape=kernel_shape,
        pads=pads,
        strides=strides,
    )

    graph_def = onnx.helper.make_graph(
        nodes=[node],
        name="Conv",
        inputs=[input],
        outputs=[output],
        initializer=[weight, bias],
    )

    onnx_model = onnx.helper.make_model(graph_def, producer_name="tinyquant-test")
    onnx_model.opset_import[0].version = 13

    onnx_model = onnx.shape_inference.infer_shapes(onnx_model)

    onnx.checker.check_model(onnx_model)

    return onnx_model