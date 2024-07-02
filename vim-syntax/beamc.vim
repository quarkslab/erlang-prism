" Vim syntax file
" Language: BEAM disassembly
" Maintainer: Damien Cauquil
" Latest: 12 September 2023

if exists("b:current_syntax")
	finish
endif

" Keywords
syn keyword beamInst func_info int_code_end call call_last call_only call_ext call_ext_last bif0 bif1 bif2 allocate allocate_heap allocate_zero allocate_heap_zero test_heap init deallocate return send remove_message timeout loop_rec loop_rec_end wait wait_timeout -m_plus -m_minus -m_times -m_div -int_div -int_rem -int_band -int_bor -int_bxor -int_bsl -int_bsr -int_bnot is_lt is_ge is_eq is_ne is_eq_exact is_ne_exact is_integer is_float is_number is_atom is_pid is_reference is_port is_nil is_binary -is_constant is_list is_nonempty_list is_tuple test_arity select_val select_tuple_arity jump catch catch_end move get_list get_tuple_element set_tuple_element -put_string put_list put_tuple put badmatch if_end case_end call_fun -make_fun is_function call_ext_only -bs_start_match -bs_get_integer -bs_get_float -bs_get_binary -bs_skip_bits -bs_test_tail -bs_save -bs_restore -bs_init -bs_final bs_put_integer bs_put_binary bs_put_float bs_put_string -bs_need_buf fclearerror fcheckerror fmove fconv fadd fsub fmul fdiv fnegate make_fun2 try try_end try_case try_case_end raise bs_init2 -bs_bits_to_bytes bs_add apply apply_last is_boolean is_function2 -bs_start_match2 bs_get_integer2 bs_get_float2 bs_get_binary2 bs_skip_bits2 bs_test_tail2 -bs_save2 -bs_restore2 gc_bif1 gc_bif2 -bs_final2 -bs_bits_to_bytes2 -put_literal is_bitstr -bs_context_to_binary bs_test_unit bs_match_string bs_init_writable bs_append bs_private_append trim bs_init_bits bs_get_utf8 bs_skip_utf8 bs_get_utf16 bs_skip_utf16 bs_get_utf32 bs_skip_utf32 bs_utf8_size bs_put_utf8 bs_utf16_size bs_put_utf16 bs_put_utf32 on_load recv_mark recv_set gc_bif3 line put_map_assoc put_map_exact is_map has_map_fields get_map_elements is_tagged_tuple build_stacktrace raw_raise get_hd get_tl put_tuple2 bs_get_tail bs_start_match3 bs_get_position bs_set_position swap bs_start_match4 make_fun3 init_yregs recv_marker_bind recv_marker_clear recv_marker_reserve recv_marker_use bs_create_bin call_fun2 nif_start badrecord update_record bs_match nextgroup=@beamOperand skipwhite

" Labels
syn match beamLabel 'label\d\+:'
syn match beamLabelRef 'label\d\+' contained nextgroup=@beamOperand skipwhite

" Values
syn match beamValue '\d\+' contained nextgroup=@beamOperand skipwhite
syn match beamValue '0x[0-9a-fA-F]\+' contained nextgroup=@beamOperand skipwhite

" X and Y Registers
syn match beamRegs 'X\d\+' contained nextgroup=@beamOperand skipwhite
syn match beamRegs 'Y\d\+' contained nextgroup=@beamOperand skipwhite

" Strings
syn region beamStr start='"' end='"' contained nextgroup=@beamOperand skipwhite

" Refs
syn region beamExtRef start='<' end='>' contained nextgroup=@beamOperand skipwhite

" Lists
syn region beamList start='\[' end='\]' fold contains=@beamOperand

" Tuples
syn region beamTuple start='(' end=')' fold contains=@beamOperand 

" Atoms
syn region beamAtom start='\'' end='\'' contained nextgroup=@beamOperand skipwhite

" Literals
syn region beamLiteral start='`' end='`' contained nextgroup=@beamOperand skipwhite

" Operators
syn match beamOperator	'=>'

" Operand cluster
syn cluster beamOperand contains=beamLabelRef,beamRegs,beamValue,beamStr,beamList,beamExtRef,beamAtom,beamTuple,beamLiteral

" Comments
syn match beamComment ';.*$'

highlight default link	beamValue	Special
highlight default link	beamRegs	Special
highlight default link 	beamLabel	Structure
highlight default link	beamLabelRef	Structure
highlight default link 	beamComment	Comment
highlight default link 	beamInst	Function
highlight default link	beamStr		Constant
highlight default link	beamList	Constant
highlight default link	beamOperator	Operator
highlight default link	beamExtRef	PreProc
highlight default link	beamAtom	Constant
highlight default link	beamLiteral	Constant

let b:current_syntax = 'beamc'

