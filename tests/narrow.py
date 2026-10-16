"""Mesures à largeur d'écran étroite (iPhone ~390 px), partagées par les tests de rendu."""

# Éléments qui sortent VISIBLEMENT de l'écran, boîte ou contenu (un texte peut déborder d'une boîte
# trop étroite). Un élément rogné par un conteneur qui défile ou masque son contenu (tableau défilant,
# rangée du menu) n'est pas compté.
OVERFLOW_JS = (
    "function __overflow(){var vw=document.documentElement.clientWidth,out=[];"
    "document.querySelectorAll('body *').forEach(function(e){var r=e.getBoundingClientRect();if(!r.height)return;"
    # bord droit du CONTENU : un texte peut déborder d'une boîte trop étroite (même de 0 px de large)
    "var cs=getComputedStyle(e),right=cs.overflowX==='visible'?Math.max(r.right,r.left+e.scrollWidth):r.right;"
    "if(right<=vw+1&&r.left>=-1)return;"
    "for(var a=e.parentElement;a&&a!==document.body;a=a.parentElement){if(getComputedStyle(a).overflowX!=='visible'){"
    "var ar=a.getBoundingClientRect();if(ar.right<=vw+1&&ar.left>=-1)return;}}"
    "out.push(e.tagName.toLowerCase()+(e.id?'#'+e.id:'')+(typeof e.className==='string'&&e.className?'.'+e.className.split(' ')[0]:'')"
    "+' '+Math.round(r.left)+'>'+Math.round(right));});return out;}"
)
