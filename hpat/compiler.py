# from .pio import PIO
from llvmlite import binding
import hpat
import hpat.hiframes
import hpat.hiframes.hiframes_untyped
import hpat.hiframes.hiframes_typed
from hpat.hiframes.hiframes_untyped import HiFramesPass
from hpat.hiframes.hiframes_typed import HiFramesTypedPass
from hpat.hiframes.dataframe_pass import DataFramePass
import numba
import numba.compiler
from numba.compiler import DefaultPassBuilder
from numba import ir_utils, ir, postproc
from numba.targets.registry import CPUDispatcher
from numba.ir_utils import guard, get_definition
from numba.inline_closurecall import inline_closure_call, InlineClosureCallPass
from numba.typed_passes import (NopythonTypeInference, AnnotateTypes, ParforPass, IRLegalization)
from numba.untyped_passes import (DeadBranchPrune, InlineInlinables, InlineClosureLikes)
from hpat import config
from hpat.distributed import DistributedPass
import hpat.io
if config._has_h5py:
    from hpat.io import pio

from numba.compiler_machinery import FunctionPass, register_pass

# workaround for Numba #3876 issue with large labels in mortgage benchmark
binding.set_option("tmp", "-non-global-value-max-name-size=2048")


def inline_calls(func_ir, _locals):
    work_list = list(func_ir.blocks.items())
    while work_list:
        label, block = work_list.pop()
        for i, instr in enumerate(block.body):
            if isinstance(instr, ir.Assign):
                lhs = instr.target
                expr = instr.value
                if isinstance(expr, ir.Expr) and expr.op == 'call':
                    func_def = guard(get_definition, func_ir, expr.func)
                    if (isinstance(func_def, (ir.Global, ir.FreeVar))
                            and isinstance(func_def.value, CPUDispatcher)):
                        py_func = func_def.value.py_func
                        inline_out = inline_closure_call(
                            func_ir, py_func.__globals__, block, i, py_func,
                            work_list=work_list)

                        # TODO remove if when inline_closure_call() output fix
                        # is merged in Numba
                        if isinstance(inline_out, tuple):
                            var_dict = inline_out[1]
                            # TODO: update '##distributed' and '##threaded' in _locals
                            _locals.update((var_dict[k].name, v)
                                           for k, v in func_def.value.locals.items()
                                           if k in var_dict)
                        # for block in new_blocks:
                        #     work_list.append(block)
                        # current block is modified, skip the rest
                        # (included in new blocks)
                        break

    # sometimes type inference fails after inlining since blocks are inserted
    # at the end and there are agg constraints (categorical_split case)
    # CFG simplification fixes this case
    func_ir.blocks = ir_utils.simplify_CFG(func_ir.blocks)

# TODO: remove these helper functions when Numba provide appropriate way to manipulate passes
def pass_position(pm, location):
    assert pm.passes
    pm._validate_pass(location)
    for idx, (x, _) in enumerate(pm.passes):
        if x == location:
            return idx

    raise ValueError("Could not find pass %s" % location)


def add_pass_before(pm, pass_cls, location):
    assert pm.passes
    pm._validate_pass(pass_cls)
    position = pass_position(pm, location)
    pm.passes.insert(position, (pass_cls, str(pass_cls)))

    # if a pass has been added, it's not finalized
    pm._finalized = False


def replace_pass(pm, pass_cls, location):
    assert pm.passes
    pm._validate_pass(pass_cls)
    position = pass_position(pm, location)
    pm[position] = (pass_cls, str(pass_cls))

    # if a pass has been added, it's not finalized
    pm._finalized = False


@register_pass(mutates_CFG=True, analysis_only=False)
class InlinePass(FunctionPass):
    _name = "hpat_inline_pass"

    def __init__(self):
        pass

    def run_pass(self, state):
        inline_calls(state.func_ir, state.locals)
        return True


@register_pass(mutates_CFG=True, analysis_only=False)
class PostprocessorPass(FunctionPass):
    _name = "hpat_postprocessor_pass"

    def __init__(self):
        pass

    def run_pass(self, state):
        post_proc = postproc.PostProcessor(state.func_ir)
        post_proc.run()
        return True


class HPATPipeline(numba.compiler.CompilerBase):
    """HPAT compiler pipeline
    """

    def define_pipelines(self):
        name = 'hpat'
        pm = DefaultPassBuilder.define_nopython_pipeline(self.state)

        add_pass_before(pm, InlinePass, InlineClosureLikes)
        pm.add_pass_after(HiFramesPass, InlinePass)
        pm.add_pass_after(DataFramePass, AnnotateTypes)
        pm.add_pass_after(PostprocessorPass, AnnotateTypes)
        pm.add_pass_after(HiFramesTypedPass, DataFramePass)
        pm.add_pass_after(DistributedPass, ParforPass)
        pm.finalize()

        return [pm]


@register_pass(mutates_CFG=True, analysis_only=False)
class ParforSeqPass(FunctionPass):
    _name = "hpat_parfor_seq_pass"

    def __init__(self):
        pass

    def run_pass(self, state):
        numba.parfor.lower_parfor_sequential(
            state.typingctx, state.func_ir, state.typemap, state.calltypes)

        return True


class HPATPipelineSeq(HPATPipeline):
    """HPAT pipeline without the distributed pass (used in rolling kernels)
    """

    def define_pipelines(self):
        name = 'hpat_seq'
        pm = DefaultPassBuilder.define_nopython_pipeline(self.state)

        add_pass_before(pm, InlinePass, InlineClosureLikes)
        pm.add_pass_after(HiFramesPass, InlinePass)
        pm.add_pass_after(DataFramePass, AnnotateTypes)
        pm.add_pass_after(PostprocessorPass, AnnotateTypes)
        pm.add_pass_after(HiFramesTypedPass, DataFramePass)
        add_pass_before(pm, ParforSeqPass, IRLegalization)
        pm.finalize()

        return [pm]
