// Load hi-fi covers
var covers = document.querySelectorAll('.source__image');
for (var i = 0; i < covers.length; i++) {
  if (covers[i].hasAttribute('data-bgSrc')) {
    covers[i].style.backgroundImage = 'url("' + covers[i].getAttribute('data-bgSrc') + '")';
  }
}

// Make highlight stand out when permalinked
var activateHighlight = function(hash) {
  var highlight = document.getElementById(hash);
  highlight.className += ' highlight--active';
  for (var i = 0; i < highlight.childNodes.length; i++) {
    if (highlight.childNodes[i].className == 'highlight__text') {
      var highlightText = highlight.childNodes[i];
      highlightText.innerHTML = '<span>' + highlightText.innerHTML + '</span> <button id="js-clearHighlight" class="btn--clear" title="Clear highlight feature"><svg viewBox="0 0 20 20" width="20" height="20"><use xlink:href="#clear"></use></svg></button>';
      svg4everybody();
      break;
    }        
  }
  highlight.focus();
};

var removeHighlight = function() {
  var highlighted = document.querySelector('.highlight--active');
  if (highlighted !== null) {
    highlighted.className = 'highlight';
    document.getElementById('js-clearHighlight').remove();
  }
};

var highlightSwitch = function(e) {
  if (e.target.tagName === 'A') {
    var targetLink = e.target.href.toString();
  } else if (e.target.parentNode.tagName === 'A') {
    var targetLink = e.target.parentNode.href.toString();
  } else if (e.target.parentNode.parentNode.tagName === 'A') {
    var targetLink = e.target.parentNode.parentNode.href.toString();
  }
  if (targetLink && targetLink.indexOf('#') > -1) {
    e.preventDefault();
    var hash = targetLink.substr(targetLink.indexOf('#') + 1);
    if (document.getElementById(hash).className.indexOf('highlight--active') === -1) {
      removeHighlight();
      activateHighlight(hash);
    }
  }
};

if (window.location.hash) {
  var hash = window.location.hash.replace('#', '');
  if (document.getElementById(hash)) {
    activateHighlight(hash);
  }
}

window.addEventListener('click', highlightSwitch, false);

// Clear featured highlight
var clickClear = function(e) {
  if (e.target.id === 'js-clearHighlight' || e.target.parentNode.id === 'js-clearHighlight') {
    removeHighlight();
    var hashIndex = window.location.href.indexOf('#');
    var hashlessURL = window.location.href.slice(0, hashIndex);
    history.replaceState(null, null, hashlessURL);
  }
}

window.addEventListener('click', clickClear, false);

// Polyfil for SVG sprites
svg4everybody();