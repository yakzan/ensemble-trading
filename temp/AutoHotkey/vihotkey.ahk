;; :encoding=utf-8:
;;
;; kbdmodal.ahk
;; 
;; author: Marko Mahnič
;; Modified By Cucumber to make it work like vi
;; purpose: to edit like vi everywhere
;;
;; command supported:
;;   	Esc: toggle between command mode and write mode
;;		in command mode:
;;			h, j, k, l: move the cursor
;;				(count prefix supported like: 4h--move 4 char left)
;;			w, b: move forward or backward one words
;;				(count prefix supported like: 4w--move 4 word forward)
;;			c-w, c-b: delete word forward or backward
;;				(count prefix supported)
;;			x, y, p: cut, copy, paste;
;;				{num}yy: copy num lines
;;			c-u, c-d: page up, page down
;;				(count prefix supported)
;;			g, G: go to first or lase line
;;				{num}g: command 9g go to the 9th line
;;			f, F, t, T: goto the char or befor the char forward or backward
;;				{count prefix supported}
;;			J: join line
;;				{count prefix supported}
;;			^, $: first or last pos of line
;;			i, a: return to write mode before the cursor or after the cursor
;;			v: select text. use h, j, k, l, w, b, g, G, ^, $ (not suopport 
;;					f, F, t, T, this four command is ignored when selecting)
;;					command to move the cursor,
;;					and text along the route will be select. 
;;					press v again or x, y, d, p to stop selecting
;;			u: undo
;;				(count prefix supported, menu of the program with redo cmd needed)
;;			c-a: select all
;;			c-z: undo
;;				(count prefix supported)
;;			c-r: redo
;;				(count prefix support, editor redo menu needed: [e]dit->[r]edo)
;;			d: dd, dl, dh, dj, dk, dw, db, d{count}g, dG, d$, d^
;;				df{ch}, dF{ch}, dt{ch}, dT{ch}
;;				(count prefix supported)
;;			y: copy. what d supports is supported like yw, yb, yy..
;;			v: select mode, use h, j, k, l, g, G, ^, $ command to select text, 
;;				press v or x, d, y, p or Esc to end select mode
;;			a, i: switch to write mode before or after the cursor
;;			o, O: open new line
;;			s, S: replace and switch to write mode
;;			r, R: replace one char and stop or until enter Esc
;;			c-a: select all
;;			c-s: save 

;; note:
;;		1. not fully tested, if the select mode goes wrong, enter ctrl-alt-s 
;;			may make it leave select mode 
;;		2. functions commented may be useful if you try to modify it. 
;;			or you can just delete it
;;		3. to make it work right, you should reset the insert key 
;;			before starting this script
;;		4. only windows add to interest_program array is mapped to vi mode
;;		5. something goes wrong, press c-q to exit the script, 
;;			c-Q to reload the script
;;		6. most control key (ctrl-, alt-) is still valid in cmd mode 
;;			if they do not conflict with this script's mapping. 
;;			if conflicted, switch to write mode to send that key
;;		7. Sleep, %safe_delay% in the script is used for eclipse when i do testing
;;			maybe because eclipse's slowness, it needs time to complete each key
;;			input 99g in command mode in eclipse and you will see how slow eclipse is


;; TODO: job marked with * is done
;*1.  escape or other toggle key
;*2.  cursor looks
;*3.  r R command
; 4.  macro record(out of my ability)
; 5.  / n N(out of my ability since every "find" menu in different editor 
;			is different)
; 6.  . command(out of my ability, esp to repeat the d command)
;*7.  select mode
; 8.  register for copy
;*9.  edit mode per window.
; 10. check window information periodicly to release memory(out of my ability)
;*11. remove mode_keypad
; 12. mark commands(out of my ability, i do not know how to get current position)
;*13. C-R (redo) command when eclipse, codeblock and so on active
; 14. regexp searching
; 15. uppercase or lowercase the char
;*16. f F t T command. (use Clipboard).
; 17. : command mode. (not neccessary)
;*18. d command improve-- dw, db, d9g... (use selection)
;*19. make it only simulate vi when editplus, eclipse, codeblock active
;*20. s, s-s command
; 21. ~ command, uppercase, lowercase command

;; Difference with vi:
;;		1. d command would not put the text deleted into clipboard
;;			not the same as in vi which can delete all the lines 
;;			along the movement
;;		2. f, t, F, T is nonecasesensitive

;; Bugs:
;;		1. command dfA does not work while dfa works
;;		

;; your can find the original script at
;;		http://www.autohotkey.com/forum/topic14428.html
;;
;; original orthor declaration:
;;
;; Author: Marko Mahnič
;; Description:
;;      Keyboard remapper with 3 modes of operation: Write, Command and
;;      Keypad. To enter the command mode press CapsLock. To enter
;;      the Kepyad mode press Alt-CapsLock. To toggle the CapsLock state
;;      press Shift-CapsLock.
;;
;;      Command mode (on english keyboard)
;;
;;      The current mode is displayed in a semi-transparent window.
;;      The prefix argument works with all movement commands and with
;;      the commands: v, w, s, d. It also works with arrow keys and
;;      the numeric keypad (NumLock Off).
;;
;; History:
;;    2006-08-19 First version
;;      - CapsLock cycles thru modes: Normal, Move, KP
;;      - Alt-CapsLock toggles CapsLock state
;;      - ijkl for arrows, np for page operations, xcv for clipboard,
;;        be for home/end
;;      - Ctrl-Z, Ctrl-S undo/save
;;      - d delete
;;    2006-09-10 Marko Mahnič
;;      - status blinks when mode is not Normal
;;      - fadeout window with mode-change info added
;;      - keyboard changes: O. page; im home/end (similar to keypad layout)
;;      - CapsLock switches between Move and KP; a returns to Normal
;;    2006-10-20 Marko Mahnič
;;      - modes renamed: Write, Command(CMD) and KP
;;      - w (Write) changes to normal, key a unassigned
;;      - s (select) pops up a selection menu (select words, lines, bol, eol)
;;      - q (quick?) waits for char input and sends ctrl-char
;;      - PREFIX argument in CMD mode for repeated keypress
;;        (type 55w# to insert 55 characters #)
;;    2006-11-19 Marko Mahnič
;;      - Suspend the script for certain windows.
;;        VMWare virtual machine doesn't recieve translated keypresses
;;        so the outer instance of the script should be suspended and
;;        a new instance should be running inside the VM.
;;    2006-11-23 Marko Mahnič
;;      - mode window in the titlebar (when not in Write mode)
;;      - CapsLock -> CMD; Alt-CapsLock -> KP; Shift-CapsLock -> toggle
;;      - a waits for char input and sends ctrl-char
;;      - code cleanup


;; -------------------------------------------
;; options:
;; -------------------------------------------

;; script would check win mode periodicly, here you can set the period
check_timeout := 100

;; set program you want to use vi simulation
interest_program := ["Code:{2}Block", "Eclipse", "EditPlus", "PDF-XChange Viewer", "SciTE4AutoHotkey"]

;; some program like eclipse needs delay to wait for key strokes complete
;; if your slowest program run faster than mine, 
;; reduce this value to make it work fast
safe_delay := 50

;; -------------------------------------------
;; following script better not be changed 
;; unless you want to change the script to work your way
;; -------------------------------------------

;opt_auto_reset_mode := true
opt_wmode_position := "WTC"
opt_window_suspend := "InVitro:"

blink_enabled := 0
blink_timeout := 500
blink_state := 0
;; dblcaps_timeout := 500

trans_blink_on := 255
trans_blink_off := 64
trans_default := 192

status_title:= "Keymode-Status"

;; If you change these also change the #ifwinexist commands !
win_title   := "Modal Keyboard"
mode_normal := "Mode: Write"
mode_move   := "Mode: Command"
mode_replace := "Mode: Replace"

;; Some system have multi-press home/end behaviour
;; jEdit: beg_of_nonwhite, bol, beg_of_screen
;; MSVC: beg_of_nonwhite, bol
;; NetBeans: beg_of_nonwhite, bol
;keyseq_bol:="{Home}{Home}"
;keyseq_eol:="{End}{End}"
;keyseq_bol_select:="+{Home}+{Home}"
;keyseq_eol_select:="+{End}+{End}"

rgui_prefer_h := 16
rfade_prefer_h := 24
rgui_w:= 90
rgui_w2:=138
rgui_h:=16			; 0 set, the win will be not visible
rfade_w:=140
rfade_h:=24

; the insert key state is associated to the app but the whole env
win_insert_state := Object()

; window respective mode info
win_mode := Object()

; function stack used for command junction
func_stack := Array()

;; used by d, y command
d_cmd_times:=0
y_cmd_times:=0

add_select_prefix := false

;; store last command to simulate . command in vi, not done
;last_edit_command := ""

make_windows()
modewin_update_position()
main_loop()
return

repeat_count := "" ; prefix argument for some commands
gid_active_window := 0
gid_win_mode := 0
gid_win_status := 0
gid_mnu_selection := 0


;; ---------------------------------------------
;; gui functions
;; ---------------------------------------------
make_windows()
{
   global gid_win_mode, gid_win_status
   global rgui_w, rgui_w2, rgui_h
   global rfade_w, rfade_h
   global win_title, status_title, mode_normal
   global ctrl_mode, ctrl_change, repeat_display
   global trans_default
   
   SysGet,rect_workarea,MonitorWorkArea
   
   rgui_top:=rect_workareaBottom - rgui_h
   rgui_left:=rect_workareaRight - rgui_w
   rmid_left:=rgui_left / 2
   rmid_top:=rgui_top / 2
   
   Gui, -Caption +Border +AlwaysOnTop +ToolWindow
   Gui, Add, Text, cRed x1 y1 w90 vctrl_mode, %mode_normal%
   Gui, Add, Text, cBlue x90 y1 w90 vrepeat_display,R:888 
   Gui, Show, NA w90 h16 x0 y0,%win_title%
   WinGet,gid_win_mode,ID,%win_title%, %mode_normal%
   WinSet,Transparent,%trans_default%,ahk_id %gid_win_mode%
   
   Gui, 2:-Caption +Border +AlwaysOnTop +ToolWindow
   Gui, 2:Font, s12 w700
   Gui, 2:Add, Text, cGreen x1 y1 w%rfade_w% vctrl_change,Status
   Gui, 2:Show, NA w%rfade_w% h%rfade_h% x0 y0,%status_title%
   WinGet,gid_win_status,ID,%status_title%,Status
   Gui, 2:Hide
}

do_modewin_update_position()
{
   global gid_win_mode, mode_normal
   global rgui_w, rgui_h, rgui_w2
   global repeat_count
   global opt_wmode_position
   global active_x,active_y,active_w,active_h
   
   SetTimer,lab_tm_update_position,Off
   
   hh := rgui_h
   ww := rgui_w
   if (repeat_count != "")
      ww := rgui_w2

   curmode := what_mode()
   
   ;; Bottom Right
   SysGet,rect_workarea,MonitorWorkArea
   xx:=rect_workareaRight - ww
   yy:=rect_workareaBottom - hh
   if (curmode != mode_normal)
   {
      if (opt_wmode_position == "WTC")
      {
         ;; Window titlw center
         xx := active_x + (active_w - ww) / 2
         yy := active_y + 8
      }
      else
         xx:=xx / 2 ;; Horizontal Center
   }

   WinMove,ahk_id %gid_win_mode%,,%xx%,%yy%,%ww%,%hh%
}

lab_tm_update_position:
{
   SetTimer,lab_tm_update_position,Off
   do_modewin_update_position()
   return
}

modewin_update_position()
{
   SetTimer,lab_tm_update_position,10
}

;; ---------------------------------------------
;; mode functions
;; ---------------------------------------------
what_mode()
{
   global ctrl_mode
   GuiControlGet,curmode,,ctrl_mode,Text
   return curmode
}

;mode_toggle()
;{
;   global mode_normal
;   st := GetKeyState("CapsLock", "T") 
;   if (st)
;   {
;      SetCapsLockState, Off
;      setmode(mode_normal, "CapsLock Off")
;   }
;   else
;   {
;      SetCapsLockState, On
;      setmode(mode_normal, "CAPSLOCK ON")
;   }
;}

setmode(new_mode, fadeout_label=0)
{
   global ctrl_mode, ctrl_change, tm_count, mode_normal
   global gid_win_mode, trans_default   
	global mode_move, win_mode

	global add_select_prefix
	old_mode := what_mode()

   SetTimer,lab_tm_fadeout,Off
   SetTimer,lab_tm_blink,Off
   GuiControl,Text,ctrl_mode,%new_mode%
   if (fadeout_label = 0)
      fadeout_label := new_mode
	
   if (new_mode == mode_normal)
      WinSet,Transparent,%trans_default%,ahk_id %gid_win_mode%
   else
      WinSet,Transparent,255,ahk_id %gid_win_mode%
   
   clear_prefix_arg()
	clear_d_cmd_times()
	clear_y_cmd_times()
	if (old_mode == mode_move && add_select_prefix)
	{
		clear_select()
		SendInput, {Left}
	}

   blink_begin()
   fadeout_begin(15,fadeout_label)
   modewin_update_position()
	
	win_id := WinExist("A")
	win_mode[win_id] := new_mode
	check_cursor_style()
}


;; ---------------------------------------------
;; Periodic checks
;; ---------------------------------------------
;check_reset_mode()
;{
;   global gid_active_window, mode_normal, win_title, gid_win_mode
;	global add_select_prefix
;   WinGet, active_id, ID, A
;
;   if (active_id != gid_active_window)
;   {
;      if not (WinExist(win_title, mode_normal))
;      {
;         if (check_window_reset())
;			{
;            setmode(mode_normal)
;				add_select_prefix := false
;			}
;      }
;      gid_active_window := active_id
;      do_modewin_update_position()
;   }
;}

;;   - if option set, always switch to user-defined mode on select
;check_window_reset()
;{
;   global opt_auto_reset_mode
;   
;   if (not opt_auto_reset_mode) 
;      return 0
;      
;   IfWinActive,Total Commander
;      return 0
;   IfWinActive,Lister 
;      return 0
;      
;   return 1
;}

;check_suspend_script()
;{
;   global mode_normal,opt_window_suspend
;   If WinActive(opt_window_suspend)
;   {
;      Suspend,On
;      setmode(mode_normal)
;      WinWaitNotActive,%opt_window_suspend%
;      Suspend,Off
;   }
;}

check_win_mode() {
	global mode_move, mode_normal, win_mode, win_insert_state
	win_id := WinExist("A")
	real_mode := what_mode()
	if (win_mode[win_id] == "")
	{
		setmode(mode_normal)
	}
	supposed_mode := win_mode[win_id]

	if (supposed_mode != real_mode)
		setmode(supposed_mode)
}

check_cursor_style() {
	global mode_move, mode_normal, win_mode, win_insert_state
	real_mode := what_mode()
	win_id := WinExist("A")
	if (win_insert_state[win_id] == "")
	{
		win_insert_state[win_id] := 0
	}

	if (real_mode == mode_move && win_insert_state[win_id] == 0)
	{
		SendInput, {Insert}
		win_insert_state[win_id] := 1
	}
	else if (real_mode == mode_normal && win_insert_state[win_id] != 0)
	{
		SendInput, {Insert}
		win_insert_state[win_id] := 0
	}
	else if (real_mode == mode_replace && win_insert_state[win_id] == 0)
	{
		SendInput, {Insert}
		win_insert_state[win_id] := 1
	}
}

check_win_mode_and_insert_state()
{
	check_win_mode()
	check_cursor_style()
}

;is_alive(id)
;{
;	DetectHiddenWindows, On
;	WinGet, ret_id, ID, ahk_id %id%
;	DetectHiddenWindows, Off
;	if (ret_id == "" || ret_id == 0)
;	{
;		return false
;	}
;	return true
;}

;; this function not always work. when it do not, the edit mode would be messed
;remove_closed_win_info()
;{
;	global win_insert_state, win_mode
;	for index, element in win_mode
;	{
;		if(!is_alive(index))
;		{
;			win_mode.Remove(index)
;		}
;	}
;	for index, element in win_insert_state
;	{
;		if(!is_alive(index))
;			win_insert_state.Remove(index)
;	}
;}

check_interested_win()
{
	global interest_program
	SetTitleMatchMode, RegEx
	for index, value in interest_program
	{
		IfWinActive, %value%
		{
			return value
		}
	}
	return ""
}

perform_periodic_checks()
{
   global active_x,active_y,active_w,active_h
	global rgui_h, rgui_prefer_h

	win_index := check_interested_win()
	if (win_index == "")
	{
		rgui_h := 0
      do_modewin_update_position()
		active_x := -100000		; reset active_x, active_y which is a impossible value
		active_y := -100000		; so when active next time mode_win will be updated
		Suspend, On
		return
	}
	Suspend, Off
	rgui_h := rgui_prefer_h

   x := active_x
   y := active_y
   WinGet, active_id, ID, A
   WinGetPos,active_x,active_y,active_w,active_h,ahk_id %active_id%
   
   if (x != active_x or y != active_y)
   {
      do_modewin_update_position()
   }

   if true
   {
      ;; check_reset_mode()
      ;; check_suspend_script()
		check_win_mode_and_insert_state()
   }
}

main_loop()
{
	global check_timeout
   Loop
   {
		perform_periodic_checks()
		Sleep, %check_timeout%
		;remove_closed_win_info()		; this function not work well because 
												; it is hard to get all wins alive
   }
}

;; ---------------------------------------------
;; Blink functions
;; ---------------------------------------------
blink_begin()
{
   global gid_win_mode, win_title, mode_normal
	global blink_enabled, blink_timeout, blink_state
   blink_state := 0
   If (WinExist(win_title, mode_normal))
   {
      blink_end()
      return
   }
   if (not blink_enabled)
   {
      blink_end()
      return
   }
     
   SetTimer,lab_tm_blink,%blink_timeout%
}

blink_end()
{
   global gid_win_mode
   global trans_blink_on, trans_blink_off, trans_default
   SetTimer,lab_tm_blink,Off
   WinSet,Transparent,%trans_default%,ahk_id %gid_win_mode%
}

blink_toggle()
{
   global gid_win_mode, blink_state
   global trans_blink_on, trans_blink_off, trans_default
   
   blink_state := 1 - blink_state
   if (blink_state)
      WinSet,Transparent,%trans_blink_on%,ahk_id %gid_win_mode%
   else
      WinSet,Transparent,%trans_blink_off%,ahk_id %gid_win_mode%
}

lab_tm_blink:
{
   if (blink_enabled)
      blink_toggle()
   
   return
}

;; ---------------------------------------------
;; fade out functions
;; ---------------------------------------------
do_fadeout_begin(fcount, fadeout_label)
{
   global gid_win_status, rfade_w, rfade_h
   global active_x,active_y,active_w,active_h
   global tm_fadeout_count
   SetTimer,lab_tm_fadeout,Off
   tm_fadeout_count := fcount
   Gui, 2:Show, NA,CapsStatusChanging
   GuiControl,2:Text,ctrl_change,%fadeout_label%
   
   rmid_left := active_x + (active_w - rfade_w) / 2
   rmid_top  := active_y + (active_h - rfade_h) / 2
   WinMove,ahk_id %gid_win_status%,,%rmid_left%,%rmid_top%
   WinSet,Transparent,220,ahk_id %gid_win_status%
   SetTimer,lab_tm_fadeout,50
}

gpar_fadeout_count:=0
gpar_fadeout_label:="..."
fadeout_begin(fcount, fadeout_label)
{
   global gpar_fadeout_count, gpar_fadeout_label
   gpar_fadeout_count := fcount
   gpar_fadeout_label := fadeout_label
   SetTimer,lab_tm_install_fadeout,100
}

lab_tm_install_fadeout:
{
   SetTimer,lab_tm_install_fadeout,Off
   do_fadeout_begin(gpar_fadeout_count, gpar_fadeout_label)
   return
}

fadeout_end()
{
   global gid_win_status
   SetTimer,lab_tm_install_fadeout,Off
   SetTimer,lab_tm_fadeout,Off
   WinHide,ahk_id %gid_win_status%
}

lab_tm_fadeout:
{
    tm_fadeout_count := tm_fadeout_count - 1
    if tm_fadeout_count < 1
    {
       fadeout_end()
       return
    }
    if (tm_fadeout_count <= 10)
    {
       n_trans := 220 - (10 - tm_fadeout_count) * 20
       WinSet,Transparent,%n_trans%,ahk_id %gid_win_status%
    }
    return
}

;;----------------------------
;;	key mapping functions 
;;	(if you hope to clear most of the state set by d, y, v command, 
;;		use key mapping funcion, if you only want to map a key, 
;;		using Sendinput makes you clear about what you have done exactly
;;		-- since key mapping function do extra work you might neglect)
;;----------------------------
;; this function has no mark "{...}"
map_key(pfx, key)
{
	global add_select_prefix
	;set_last_edit_command("", key)

	t_add_select_prefix := add_select_prefix
	t_whether_end_select := whether_end_select_behaviour(pfx, key)
	if (t_add_select_prefix && !t_whether_end_select)
		SendInput, {Shift Down}

   SendInput {blind}%pfx%%key%

	if (t_add_select_prefix && !t_whether_end_select)
		SendInput, {Shift Up}
	if (t_add_select_prefix && t_whether_end_select)
		clear_select()

	clear_prefix_arg()
	clear_d_cmd_times()
	clear_y_cmd_times()
}

;; only special key like {PgDn} can be mapped for the mark"{...}" in function
map_key_repeat(pfx, key, func=0)
{
   global repeat_count
	global add_select_prefix

   fadeout_end()
   
	t_add_select_prefix := add_select_prefix
	t_whether_end_select := whether_end_select_behaviour(pfx, key)
	if (t_add_select_prefix && !t_whether_end_select)
		SendInput, {Shift Down}

   if (repeat_count == "")
		repeat_count := 1
	
	if (IsFunc(func))
		loop, %repeat_count%
			func.()
	else
	{
		SendInput %pfx%{%key% %repeat_count%}
	}

	if (t_add_select_prefix && !t_whether_end_select)
		SendInput, {Shift Up}
	if (t_whether_end_select)
		clear_select()

	clear_prefix_arg()
	clear_d_cmd_times()
	clear_y_cmd_times()
}

is_move_command(pfx, key)
{
	StringGetPos, pos, key, Up, L1
	if (pos >= 0)
		return true
	StringGetPos, pos, key, Down, L1
	if (pos >= 0)
		return true
	StringGetPos, pos, key, Left, L1
	if (pos >= 0)
		return true
	StringGetPos, pos, key, Right, L1
	if (pos >= 0)
		return true
	StringGetPos, pos, key, Pg, L1
	if (pos >= 0)
		return true
	StringGetPos, pos, key, Home, L1
	if (pos >= 0)
		return true
	StringGetPos, pos, key, End, L1
	if (pos >= 0)
		return true

	return false
}

whether_end_select_behaviour(pfx, key)
{
	if (is_move_command(pfx, key))
		return false
	return true
}

clear_prefix_arg()
{
   global repeat_count, repeat_display
   if (repeat_count == "") 
      return
   repeat_count := ""
   GuiControl,Text,repeat_display,
   modewin_update_position()
}

add_prefix_arg(key)
{
   global repeat_count, repeat_display
   if (StrLen(repeat_count) > 4)
   {
      clear_prefix_arg()
      return
   }

   repeat_count=%repeat_count%%key%
   GuiControl,Text,repeat_display,R:%repeat_count%
   modewin_update_position()
   a=Count: %repeat_count%
   fadeout_begin(15, a)
}

is_edit_command()
{
}

;; ---------------------------------------------
;; command functions
;; ---------------------------------------------

clear_select()
{
	global add_select_prefix
	add_select_prefix := false
	;SendInput, {Left}
	;SendInput, {Down}
	;SendInput, {Up}
}

clear_d_cmd_times()
{
	global d_cmd_times
	d_cmd_times := 0
}

clear_y_cmd_times()
{
	global y_cmd_times
	y_cmd_times := 0
}

;; deal with y, d
;; args := {y_cmd_times, d_cmd_times}
do_special_key_start(args*)
{
	global add_select_prefix
	l_y_cmd_times := args[1]
	l_d_cmd_times := args[2]
	if (l_d_cmd_times != 0 || l_y_cmd_times != 0)
	{
		add_select_prefix := true
	}
}

; in functions, using SendInput orther than map_key funcion is recommanded
; because map_key funcion may do some extra work you don't need
do_special_key_end(args*)
{
	global safe_delay
	Sleep, %safe_delay%
	global add_select_prefix
	l_y_cmd_times := args[1]
	l_d_cmd_times := args[2]
	if (l_y_cmd_times != 0)
	{
		SendInput, ^c
		clear_y_cmd_times()
		clear_d_cmd_times()
		clear_prefix_arg()
		clear_select()
		SendInput, {Left}
	}
	else if (l_d_cmd_times != 0)
	{
		SendInput, {Del}
		clear_y_cmd_times()
		clear_d_cmd_times()
		clear_prefix_arg()
		add_select_prefix := false
	}
}

do_d()
{
	SendInput, {Delete}
}

do_y()
{
	SendInput, ^c
}

do_x()
{
	global safe_delay
	SendInput, +{Right}
	Sleep, %safe_delay%
	SendInput, ^x
}

do_P()
{
	SendInput, ^v{Left}
}

kill_line()
{
	global safe_delay
	SendInput,{Home}{Home}
	SendInput,+{End}+{End}
	Sleep, %safe_delay%
	SendInput,{Del}
	Sleep, %safe_delay%
	SendInput,{Del}
}

;; ---------------------------------------------
;; 
;; ---------------------------------------------

num_to_dec(h)
{
	SetFormat, integer, dec
	d := h+0
	return %d% 
} 

num_to_hex(d)
{
	SetFormat, integer, hex
	h := d + 0
	h = %h%
	SetFormat, integer, dec ;恢复至正常的10进制计算习惯
	return %h% 
}

;; ---------------------------------------------
;; Permanent keymappings
;; Should not be present in any other section
;; ---------------------------------------------

;; Moving with keypad - repeated keypress
NumpadHome::
{
	map_key_repeat("", "Home")
}
return

NumpadUp::
{
	map_key_repeat("", "Up")
}
return

NumpadPgUp::
{
	map_key_repeat("", "PgUp")
}
return

NumpadLeft::
{
	map_key_repeat("", "Left")
}
return

NumpadClear::
{
	map_key_repeat("", "Down")
}
return

NumpadRight::
{
	map_key_repeat("", "Right")
}
return

NumpadEnd::
{
	map_key_repeat("", "End")
}
return

NumpadDown::
{
	map_key_repeat("", "Down")
}
return

NumpadPgDn::
{
	map_key_repeat("", "PgDn")
}
return

NumpadIns::
return

NumpadDel::
{
	map_key_repeat("", "Del")
}
return

Home::
{
	map_key_repeat("", "Home")
}
return

Up::
{
	map_key_repeat("", "Up")
}
return

PgUp::
{
	map_key_repeat("", "PgUp")
}
return

Left::
{
	map_key_repeat("", "Left")
}
return

Right::
{
	map_key_repeat("", "Right")
}
return

End::
{
	map_key_repeat("", "End")
}
return

Down::
{
	map_key_repeat("", "Down")
}
return

PgDn::
{
	map_key_repeat("", "PgDn")
}
return

Del::
{
	map_key_repeat("", "Del")
}
return

;; set insert key as unusable for origin use to simulate vi fully
;	here use insert key to change the cursor style according to edit mode
*Insert::
return

;;
^q::ExitApp
^+q::Reload
return

^!i::
{
	t := WinExist("A")
	Msgbox,%t%
}
return

;; ---------------------------------------------
;; Nonmapped mode
;; ---------------------------------------------
#ifwinexist Modal Keyboard, Mode: Write

;*CapsLock::
;{
;   if (getKeyState("Shift"))
;      mode_toggle()
;   else
;      setmode(mode_move)
;}
;return

*Esc::
{
	setmode(mode_move)
}
return

;; ---------------------------------------------
;; Movement block emulation (jkl)
;; ---------------------------------------------
#ifwinexist Modal Keyboard, Mode: Command
; disable unused keys
q::
;w::
e::
;r::
;t::
;y::
;u::
;i::
;o::
;p::
SC01A::         ; left bracket    ([)
SC01B::         ; right bracket   (])
*a::
;s::
;d::
;f::
;g::
;h::
;j::
;k::
;l::
SC027::        ; semicolon        (;)
SC028::        ; single quote     (') 
SC02B::        ; backslash        (\)
z::
;x::
c::
;v::
;b::
n::
m::
SC033::       ; period
SC034::       ; comma
SC029:: 		; Cedilla, left of '1'
SC039::			; space
return

+q::
+w::
+e::
;+r::
;+t::
+y::
+u::
+i::
;+o::
;+p::
+SC01A::         ; left bracket    ([)
+SC01B::         ; right bracket   (])
+a::
;+s::
+d::
;+f::
;+g::
+h::
;+j::
+k::
+l::
+SC027::        ; semicolon        (;)
+SC028::        ; single quote     (') 
+SC02B::        ; backslash        (\)
+z::
+x::
+c::
+v::
+b::
+n::
+m::
+SC033::       ; period
+SC034::       ; comma
+SC029:: 		; Cedilla, left of '1'
+SC039::			; space
return

+0::
+1::
+2::
+3::
;+4::				;$
+5::
;+6::				;^
+7::
+8::
+9::
*-::
*=::
*`::
return

;; Prefix argument
;; First we define each key to remap to itself
;; Then we add special behaviour for non-modified keypress
;*1::1
1::add_prefix_arg("1")
;*2::2
2::add_prefix_arg("2")
;*3::3
3::add_prefix_arg("3")
;*4::4
4::add_prefix_arg("4")
;*5::5
5::add_prefix_arg("5")
;*6::6
6::add_prefix_arg("6")
;*7::7
7::add_prefix_arg("7")
;*8::8
8::add_prefix_arg("8")
;*9::9
9::add_prefix_arg("9")
;*0::0
0::add_prefix_arg("0")
return

;.::SendInput,%last_edit_command%
;return

; The movement block
h::
{
	l_y_cmd_times := y_cmd_times
	l_d_cmd_times := d_cmd_times
	do_special_key_start(l_y_cmd_times, l_d_cmd_times)
	map_key_repeat("", "Left")
	do_special_key_end(l_y_cmd_times, l_d_cmd_times)
}
return

j::
{
	l_y_cmd_times := y_cmd_times
	l_d_cmd_times := d_cmd_times
	do_special_key_start(l_y_cmd_times, l_d_cmd_times)
	map_key_repeat("", "Down")
	do_special_key_end(l_y_cmd_times, l_d_cmd_times)
}
return

k::
{
	l_y_cmd_times := y_cmd_times
	l_d_cmd_times := d_cmd_times
	do_special_key_start(l_y_cmd_times, l_d_cmd_times)
	map_key_repeat("", "Up")
	do_special_key_end(l_y_cmd_times, l_d_cmd_times)
}
return

l::
{
	l_y_cmd_times := y_cmd_times
	l_d_cmd_times := d_cmd_times
	do_special_key_start(l_y_cmd_times, l_d_cmd_times)
	map_key_repeat("", "Right")
	do_special_key_end(l_y_cmd_times, l_d_cmd_times)
}
return

w::
{
	l_y_cmd_times := y_cmd_times
	l_d_cmd_times := d_cmd_times
	do_special_key_start(l_y_cmd_times, l_d_cmd_times)
	map_key_repeat("^", "Right")
	do_special_key_end(l_y_cmd_times, l_d_cmd_times)
}
return

b::
{
	l_y_cmd_times := y_cmd_times
	l_d_cmd_times := d_cmd_times
	do_special_key_start(l_y_cmd_times, l_d_cmd_times)
	map_key_repeat("^", "Left")
	do_special_key_end(l_y_cmd_times, l_d_cmd_times)
}
return

+^::
{
	l_y_cmd_times := y_cmd_times
	l_d_cmd_times := d_cmd_times
	do_special_key_start(l_y_cmd_times, l_d_cmd_times)
	map_key("", "{Home}{Home}")
	Sleep, %safe_delay%
	if (l_y_cmd_times == 0 && l_d_cmd_times == 0 && !add_select_prefix)
		SendInput, {Home}{Home}					; clear select
	do_special_key_end(l_y_cmd_times, l_d_cmd_times)
}
return

+$::
{
	l_y_cmd_times := y_cmd_times
	l_d_cmd_times := d_cmd_times
	do_special_key_start(l_y_cmd_times, l_d_cmd_times)
	map_key("", "{End}{End}")
	if (l_y_cmd_times == 0 && l_d_cmd_times == 0 && !add_select_prefix)
		SendInput, {End}{End}				; clear select
	do_special_key_end(l_y_cmd_times, l_d_cmd_times)
}
return

^d::
{
	map_key_repeat("", "PgDn")
}
return

^u::
{
	map_key_repeat("", "PgUp")
}
return

^w::
{
	map_key_repeat("^", "Del")
}
return

^b::
{
	map_key_repeat("^", "Backspace")
}
return

^s::
{
	map_key_repeat("^", "s")
}
return

; Clipboard shortcuts
^a::
{
	map_key_repeat("^", "a")
}
return

x::
{
	if (add_select_prefix)
	{
		map_key("^", "x")
		return
	}
	map_key_repeat("","", "do_x")
}
return

y::
{
	if (y_cmd_times != 0)
	{
		clear_y_cmd_times()
		SendInput, {Home}{Home}
		map_key_repeat("+", "Down")
		Sleep, %safe_delay%
		SendInput, ^c
		SendInput, {Left}
		return
	}
	else if (d_cmd_times != 0)
	{
		clear_d_cmd_times()
	}
	y_cmd_times += 1		; if in select mode, 
								;d_cmd_times will be clear in map_key_repeat function
	if (add_select_prefix)
	{
		map_key("^", "c")
		SendInput, {Left}
		return
	}
}
return

d::
{
	if (d_cmd_times != 0)
	{
		clear_d_cmd_times()
		SendInput, {Home}{Home}
		map_key_repeat("+", "Down")
		SendInput, {Del}
		return
	}
	else if (y_cmd_times != 0)
	{
		clear_y_cmd_times()
	}
	d_cmd_times += 1	; if in select mode, 
							; d_cmd_times will be clear in map_key_repeat function
	if (add_select_prefix)
	{
		map_key("", "{Del}")
		return
	}
}
return

p::
{
	if (add_select_prefix)
	{
		map_key_repeat("^", "v")
		return
	}
	SendInput, {Right}
	map_key_repeat("^", "v")
	SendInput, {Left}
}
return

+p::
{
	if (add_select_prefix)
	{
		map_key_repeat("", "", "do_P")
		return
	}
	map_key_repeat("", "", "do_P")
}
return

^z::
{
	map_key_repeat("^","z")
}
return

u::
{
	map_key_repeat("^","z")
}
return

^r::
{
	if (add_select_prefix)
	{
		clear_select()
		SendInput {Home}{Home}
	}
	clear_d_cmd_times()
	clear_y_cmd_times()
	if (repeat_count == "")
		repeat_count := 1
	loop %repeat_count%
		SendInput !er
	clear_prefix_arg()
}
return

t::
{
	if (add_select_prefix)
		return
	l_y_cmd_times := y_cmd_times
	l_d_cmd_times := d_cmd_times
	Suspend, On
	input, ch, L1
	Suspend, Off
	clipboard_backup := clipboard
	nth := repeat_count
	if (nth == "")
		nth := 1
	clear_prefix_arg()

	SendInput, {Right}
	SendInput, +{END}
	Sleep, %safe_delay%
	SendInput, ^c
	Sleep, %safe_delay%
	str := clipboard
	StringGetPos, pos, str, %ch%, L%nth%
	pos -= 1							; the only difference with f command
	SendInput, {Left}
	if (pos < 0)
	{
		map_key("", "{Left}") ; use map_key, which clears d, y command state
		return
	}

	repeat_count := pos
	if (l_y_cmd_times != 0 || l_d_cmd_times != 0)
	{
		SendInput, {Left}
		repeat_count += 2
	}
	do_special_key_start(l_y_cmd_times, l_d_cmd_times)
	map_key_repeat("", "Right")
	clipboard := clipboard_backup 
	do_special_key_end(l_y_cmd_times, l_d_cmd_times)
}
return

+t::
{
	if (add_select_prefix)
		return
	l_y_cmd_times := y_cmd_times
	l_d_cmd_times := d_cmd_times
	Suspend, On
	input, ch, L1
	Suspend, Off
	clipboard_backup := clipboard
	nth := repeat_count
	if (nth == "")
		nth := 1
	clear_prefix_arg()
	SendInput, +{Home}+{Home}
	Sleep, %safe_delay%
	map_key("^", "c")
	Sleep, %safe_delay%
	str := clipboard
	StringGetPos, pos, str, %ch%, R%nth%
	if (pos >= 0)			; only difference with F
		pos += 1
	StringLen, len, str
	SendInput, {Right}
	if (pos < 0)
		return

	repeat_count := len - pos
	do_special_key_start(l_y_cmd_times, l_d_cmd_times)
	map_key_repeat("", "Left")
	clipboard := clipboard_backup 
	do_special_key_end(l_y_cmd_times, l_d_cmd_times)
}
return

f::
{
	if (add_select_prefix)
		return
	l_y_cmd_times := y_cmd_times
	l_d_cmd_times := d_cmd_times
	Suspend, On
	input, ch, L1
	Suspend, Off
	clipboard_backup := clipboard
	nth := repeat_count
	if (nth == "")
		nth := 1
	clear_prefix_arg()

	SendInput, {Right}
	SendInput, +{END}
	Sleep, %safe_delay%		; amazing that script can only work in eclipse this delay added
	SendInput, ^c
	Sleep, %safe_delay%
	str := clipboard
	StringGetPos, pos, str, %ch%, L%nth%
	SendInput, {Left}
	if (pos < 0)
	{
		clipboard := clipboard_backup 
		map_key("", "{Left}") ; use map_key, which clears d, y command state
		return
	}

	repeat_count := pos
	if (l_y_cmd_times != 0 || l_d_cmd_times != 0)
	{
		SendInput, {Left}
		repeat_count += 2
	}
	do_special_key_start(l_y_cmd_times, l_d_cmd_times)
	map_key_repeat("", "Right")
	clipboard := clipboard_backup 
	do_special_key_end(l_y_cmd_times, l_d_cmd_times)
}
return

+f::
{
	if (add_select_prefix)
		return
	l_y_cmd_times := y_cmd_times
	l_d_cmd_times := d_cmd_times
	Suspend, On
	input, ch, L1
	Suspend, Off
	clipboard_backup := clipboard
	nth := repeat_count
	if (nth == "")
		nth := 1
	clear_prefix_arg()
	SendInput, +{Home}+{Home}
	Sleep, %safe_delay%
	map_key("^", "c")
	Sleep, %safe_delay%
	str := clipboard
	StringGetPos, pos, str, %ch%, R%nth%
	StringLen, len, str
	SendInput, {Right}
	if (pos < 0)
		return

	repeat_count := len - pos
	do_special_key_start(l_y_cmd_times, l_d_cmd_times)
	map_key_repeat("", "Left")
	clipboard := clipboard_backup 
	do_special_key_end(l_y_cmd_times, l_d_cmd_times)
}
return

Del::
{
	map_key_repeat("", "Del")
}
return

Backspace::
{
	map_key_repeat("", "Backspace")
}
return

*Esc::
{
	setmode(mode_move)
}
return

i::
{
	setmode(mode_normal)
}
return

s::
{
	map_key("", "{Del}")
	setmode(mode_normal)
}
return

+s::
{
	if (add_select_prefix)
		map_key("", "{Del}")
	setmode(mode_normal)
	SendInput,{End}{End}
	SendInput,+{Home}+{Home}
	SendInput,{Del}
}
return

r::
{
	Suspend, On
	input, ch, L1
	Suspend, Off
	map_key_repeat("", ch)
}
return

+r::
{
	setmode(mode_replace)
}
return

a::
{
   setmode(mode_normal)
	SendInput {Right}
}
return

o::
{
   setmode(mode_normal)
   SendInput,{End}{End}
   SendInput,{Enter}
}
return

+o::
{
   setmode(mode_normal)
   SendInput,{Up}
   SendInput,{End}{End}
   SendInput,{Enter}
}
return

^k::
{
	if (add_select_prefix)
	{
		clear_select()
		SendInput, {Home}{Home}
	}
	else
		map_key_repeat("","", "kill_line")
}
return

g::
{
	l_y_cmd_times := y_cmd_times
	l_d_cmd_times := d_cmd_times
	do_special_key_start(l_y_cmd_times, l_d_cmd_times)
	if (add_select_prefix)
		SendInput, ^+{Home}
	else
		SendInput, ^{Home}

	if (repeat_count == "")
		repeat_count := 1
	repeat_count -= 1
	map_key_repeat("", "Down")
	do_special_key_end(l_y_cmd_times, l_d_cmd_times)
}
return

+g::
{
	l_y_cmd_times := y_cmd_times
	l_d_cmd_times := d_cmd_times
	do_special_key_start(l_y_cmd_times, l_d_cmd_times)
	map_key_repeat("^", "End")
	do_special_key_end(l_y_cmd_times, l_d_cmd_times)
	SendInput, {Down}
}
return

+j::
{
	if (add_select_prefix)
	{
		clear_select()
		SendInput, {Home}{Home}
	}
	map_key_repeat("", "", "join_line")
}
return

; in some text editor it does not work correctly
; for the reason that the editor treat End as the End of line in screen
; when one long ling cover several lines wrapped in screen, 
; this function may not work correctly
join_line(params*)
{
	SendInput,{End}{End}
	SendInput,{Del}
}
return

;;visual mode implementation.
v::
{
	add_select_prefix := !add_select_prefix
}
return

#ifwinexist Modal Keyboard, Mode: Replace
*Esc::
{
	setmode(mode_move)
}
