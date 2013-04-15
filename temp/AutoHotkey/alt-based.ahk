;==============================
;Init
;==============================
#SingleInstance

#NoEnv
SendMode Input
SetWorkingDir %A_ScriptDir%

;==============================
; Process Move Down
;==============================
$!J::
  Send, {Down}
  return

;==============================
; Process Move Up
;==============================
$!K::
  Send, {Up}
  return

;==============================
; Process Move Left
;==============================
$!h::
  Send, {Left}
  return

;==============================
; Process Move Right
;==============================
$!l::
  Send, {Right}
  return

;==============================
; Process Jump Left
;==============================
$!n::
  Send, ^{Left}
  return

;==============================
; Process Jump Right
;==============================
$!.::
  Send, ^{Right}
  return

;==============================
; Process select Jump Left
;==============================
$!+n::
  Send, ^+{Left}
  return

;==============================
; Process select Jump Right
;==============================
$!+.::
  Send, ^+{Right}
  return

;==============================
; Process Select Down
;==============================
$!+J::
  Send, +{Down}
  return

;==============================
; Process Select Up
;==============================
$!+K::
  Send, +{Up}
  return

;==============================
; Process Select Left
;==============================
$!+h::
  Send, +{Left}
  return

;==============================
; Process Select Right
;==============================
$!+l::
  Send, +{Right}
  return

;========================== 
;Process Home 
;========================== 
$!y:: 
    Send, {Home} 
    return

;========================== 
;Process End 
;========================== 
$!o:: 
    Send, {End} 
    return

;========================== 
;Process Select to home 
;========================== 
$!+y:: 
    Send, +{Home} 
    return

;========================== 
;Process Select to end 
;========================== 
$!+o:: 
    Send, +{End} 
    return

;========================== 
;Process page up 
;========================== 
$!i:: 
    Send, {PgUp} 
    return

$!^i:: 
    Send, ^{PgUp} 
    return

;========================== 
;Process page down 
;========================== 
$!u:: 
    Send, {PgDn} 
    return

$!^u:: 
    Send, ^{PgDn} 
    return

$!6:: 
    Send, ^{Home} 
    return

$!9:: 
    Send, ^{End} 
    return

