var template = `
<div class="menu" contenteditable="false">
    <div class="group">
        <div data-action="bold"  class="item">
        <i class="fa fa-bold">
        <img class="intLink" title="Bold" src="data:image/gif;base64,R0lGODlhFgAWAID/AMDAwAAAACH5BAEAAAAALAAAAAAWABYAQAInhI+pa+H9mJy0LhdgtrxzDG5WGFVk6aXqyk6Y9kXvKKNuLbb6zgMFADs=" />
        </i></div>
        <div data-action="italic"  class="item">
        <i class="fa fa-italic">
        <img class="intLink" title="Italic" src="data:image/gif;base64,R0lGODlhFgAWAKEDAAAAAF9vj5WIbf///yH5BAEAAAMALAAAAAAWABYAAAIjnI+py+0Po5x0gXvruEKHrF2BB1YiCWgbMFIYpsbyTNd2UwAAOw==" />
        </i></div>
        <div data-action="underline"  class="item">
        <i class="fa fa-underline">
<img class="intLink" title="Underline" src="data:image/gif;base64,R0lGODlhFgAWAKECAAAAAF9vj////////yH5BAEAAAIALAAAAAAWABYAAAIrlI+py+0Po5zUgAsEzvEeL4Ea15EiJJ5PSqJmuwKBEKgxVuXWtun+DwxCCgA7" />
        </i></div>
    </div>
    <div class="group">
        <div id="makeLink" data-action="makeLink" class="item">
        <i class="fa fa-link">
<img class="intLink" title="Hyperlink" src="data:image/gif;base64,R0lGODlhFgAWAOMKAB1ChDRLY19vj3mOrpGjuaezxrCztb/I19Ha7Pv8/f///////////////////////yH5BAEKAA8ALAAAAAAWABYAAARY8MlJq7046827/2BYIQVhHg9pEgVGIklyDEUBy/RlE4FQF4dCj2AQXAiJQDCWQCAEBwIioEMQBgSAFhDAGghGi9XgHAhMNoSZgJkJei33UESv2+/4vD4TAQA7" />
        </i></div>
        <div data-action="makeOrderedList"  class="item">
        <i class="fa fa-list">
<img class="intLink" title="Numbered list" src="data:image/gif;base64,R0lGODlhFgAWAMIGAAAAADljwliE35GjuaezxtHa7P///////yH5BAEAAAcALAAAAAAWABYAAAM2eLrc/jDKSespwjoRFvggCBUBoTFBeq6QIAysQnRHaEOzyaZ07Lu9lUBnC0UGQU1K52s6n5oEADs=" />
        </i></div>
        <div data-action="makeOrderedList"  class="item">
        <i class="fa fa-list">
<img class="intLink" title="Dotted list" src="data:image/gif;base64,R0lGODlhFgAWAMIGAAAAAB1ChF9vj1iE33mOrqezxv///////yH5BAEAAAcALAAAAAAWABYAAAMyeLrc/jDKSesppNhGRlBAKIZRERBbqm6YtnbfMY7lud64UwiuKnigGQliQuWOyKQykgAAOw==" />
        </i></div>
        <div id="insertImage" data-action="insertImage"  class="item">
            <i class="fa fa-picture-o">
<svg viewBox="0 0 2252.8 2628.2667" preserveAspectRatio="xMidYMid meet" height="22" width="22" focusable="false" aria-hidden="true"> <path style="fill:#626262" d="m 1826.4,798.13336 q 28,28 48,76 20,48 20,88 V 2114.1334 q 0,40 -28,68 -28,28 -68,28 h -1344 q -40,0 -68,-28 -28,-28 -28,-68 V 514.13333 q 0,-40 28,-68 28,-28 68,-28 h 896 q 40,0 88,20 48,20 76,48 z m -444,-244.00003 v 376.00003 h 376 q -10,-29 -22,-41 l -313,-313.00003 q -12,-12 -41,-22 z m 384,1528.00007 v -1024 h -416 q -40,0 -68,-28 -28,-28 -28,-68.00004 V 546.13333 h -768 V 2082.1334 Z m -128,-448 v 320 h -1024 v -192 l 192,-192 128,128 384,-384 z m -832,-192 q -80,0 -136,-56 -56,-56 -56,-136 0,-80 56,-136 56,-56 136,-56 80,0 136,56 56,56 56,136 0,80 -56,136 -56,56 -136,56 z" /></svg>
            </i>
        </div>
        <div id="insertHR" data-action="insertHR"  class="item">
            <i class="fa fa-picture-o"><svg aria-hidden="true" focusable="false" width="15px" height="15px" preserveAspectRatio="xMidYMid meet" viewBox="0 0 16 16"><g fill="#626262"><path fill-rule="evenodd" clip-rule="evenodd" d="M6.432 10h.823V4h-.823v2.61h-2.61V4H3v6h.823V7.394h2.61V10zm5.668 0h.9l-1.28-2.63c.131-.058.26-.134.389-.23a1.666 1.666 0 0 0 .585-.797c.064-.171.096-.364.096-.58a1.77 1.77 0 0 0-.082-.557a1.644 1.644 0 0 0-.22-.446a1.504 1.504 0 0 0-.31-.341a1.864 1.864 0 0 0-.737-.373A1.446 1.446 0 0 0 11.1 4H8.64v6h.824V7.518h1.467L12.1 10zm-.681-3.32a.874.874 0 0 1-.293.055H9.463V4.787h1.663a.87.87 0 0 1 .576.24a.956.956 0 0 1 .306.737c0 .168-.029.314-.087.437a.91.91 0 0 1-.503.479zM13 12H3v1h10v-1z"/></g><rect x="0" y="0" width="16" height="16" fill="rgba(0, 0, 0, 0)" /></svg></i>
        </div>
        <div id="code" data-action="code"  class="item">
            <i class="fa fa-picture-o">
<svg viewBox="0 0 29.333333 29.333333" preserveAspectRatio="xMidYMid meet" height="22" width="22" focusable="false" aria-hidden="true"><path style="fill:#626262;stroke-width:1.29131353" d="M 13.375353,9.5014123 8.2100987,14.666667 13.375353,19.831921 12.084039,22.414548 4.3361582,14.666667 12.084039,6.9187847 Z m 2.582627,10.3305087 5.165254,-5.165254 -5.165254,-5.1652548 1.291314,-2.5826275 7.747881,7.7478823 -7.747881,7.747881 z" /></svg>
            </i>
        </div>
        <div id="quote" data-action="quote"  class="item">
            <i class="fa fa-picture-o">
<img class="intLink" title="Quote" src="data:image/gif;base64,R0lGODlhFgAWAIQXAC1NqjFRjkBgmT9nqUJnsk9xrFJ7u2R9qmKBt1iGzHmOrm6Sz4OXw3Odz4Cl2ZSnw6KxyqO306K63bG70bTB0rDI3bvI4P///////////////////////////////////yH5BAEKAB8ALAAAAAAWABYAAAVP4CeOZGmeaKqubEs2CekkErvEI1zZuOgYFlakECEZFi0GgTGKEBATFmJAVXweVOoKEQgABB9IQDCmrLpjETrQQlhHjINrTq/b7/i8fp8PAQA7" />
            </i>
        </div>
        <div data-action="increaseQuoteLevel"  class="item">
        <i class="fa fa-quote-right">
<img class="intLink" title="Add indentation" src="data:image/gif;base64,R0lGODlhFgAWAOMIAAAAADljwl9vj1iE35GjuaezxtDV3NHa7P///////////////////////////////yH5BAEAAAgALAAAAAAWABYAAAQ7EMlJq704650B/x8gemMpgugwHJNZXodKsO5oqUOgo5KhBwWESyMQsCRDHu9VOyk5TM9zSpFSr9gsJwIAOw==" />
        </i></div>
        <div data-action="increaseQuoteLevel"  class="item">
        <i class="fa fa-quote-right">
<img class="intLink" title="Delete indentation" src="data:image/gif;base64,R0lGODlhFgAWAMIHAAAAADljwliE35GjuaezxtDV3NHa7P///yH5BAEAAAcALAAAAAAWABYAAAM2eLrc/jDKCQG9F2i7u8agQgyK1z2EIBil+TWqEMxhMczsYVJ3e4ahk+sFnAgtxSQDqWw6n5cEADs=" />
        </i></div>
    </div>

    <div class="group">
        <div data-action="makeHeading"  data-action="" class="item">
        <i><b class="fa fa-header">
<svg viewBox="0 0 36.2 36.2" preserveAspectRatio="xMidYMid meet" height="22" width="22" focusable="false" aria-hidden="true"><path style="fill:#626262;stroke-width:1.50202966" d="m 26.612178,28.857712 h -4.50609 v -9.012178 h -9.012176 v 9.012178 H 8.5878225 V 6.342288 h 4.5060885 v 8.997157 h 9.012177 V 6.342288 h 4.506089 z" /></svg>
        </b></i></div>
        <div data-action="alignLeft"  data-action="" class="item">
        <i class="fa fa-align-left">
<img class="intLink" title="Left align" src="data:image/gif;base64,R0lGODlhFgAWAID/AMDAwAAAACH5BAEAAAAALAAAAAAWABYAQAIghI+py+0Po5y02ouz3jL4D4JMGELkGYxo+qzl4nKyXAAAOw==" />
        </i></div>
        <div data-action="alignCenter"  data-action="" class="item">
        <i class="fa fa-align-center">
<img class="intLink" title="Center align" src="data:image/gif;base64,R0lGODlhFgAWAID/AMDAwAAAACH5BAEAAAAALAAAAAAWABYAQAIfhI+py+0Po5y02ouz3jL4D4JOGI7kaZ5Bqn4sycVbAQA7" />
        </i></div>
        <div data-action="alignRight"  data-action=""class="item">
        <i class="fa fa-align-right">
<img class="intLink" title="Right align" src="data:image/gif;base64,R0lGODlhFgAWAID/AMDAwAAAACH5BAEAAAAALAAAAAAWABYAQAIghI+py+0Po5y02ouz3jL4D4JQGDLkGYxouqzl43JyVgAAOw==" />
        </i></div>
    </div>
    
    <div class="group">
        <div data-action="undo"  class="item">
<img class="intLink fa fa-undo" title="Undo" src="data:image/gif;base64,R0lGODlhFgAWAOMKADljwliE33mOrpGjuYKl8aezxqPD+7/I19DV3NHa7P///////////////////////yH5BAEKAA8ALAAAAAAWABYAAARR8MlJq7046807TkaYeJJBnES4EeUJvIGapWYAC0CsocQ7SDlWJkAkCA6ToMYWIARGQF3mRQVIEjkkSVLIbSfEwhdRIH4fh/DZMICe3/C4nBQBADs=" />
        </div>
        <div data-action="redo"  class="item">
        <i class="fa fa-undo flip">
<img class="intLink" title="Redo" src="data:image/gif;base64,R0lGODlhFgAWAMIHAB1ChDljwl9vj1iE34Kl8aPD+7/I1////yH5BAEKAAcALAAAAAAWABYAAANKeLrc/jDKSesyphi7SiEgsVXZEATDICqBVJjpqWZt9NaEDNbQK1wCQsxlYnxMAImhyDoFAElJasRRvAZVRqqQXUy7Cgx4TC6bswkAOw==" />
        </i></div>
        <div data-action="clear"  class="item">
        <i class="fa fa-clear flip">
<img class="intLink" title="Remove formatting" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABYAAAAWCAYAAADEtGw7AAAABGdBTUEAALGPC/xhBQAAAAZiS0dEAP8A/wD/oL2nkwAAAAlwSFlzAAAOxAAADsQBlSsOGwAAAAd0SU1FB9oECQMCKPI8CIIAAAAIdEVYdENvbW1lbnQA9syWvwAAAuhJREFUOMtjYBgFxAB501ZWBvVaL2nHnlmk6mXCJbF69zU+Hz/9fB5O1lx+bg45qhl8/fYr5it3XrP/YWTUvvvk3VeqGXz70TvbJy8+Wv39+2/Hz19/mGwjZzuTYjALuoBv9jImaXHeyD3H7kU8fPj2ICML8z92dlbtMzdeiG3fco7J08foH1kurkm3E9iw54YvKwuTuom+LPt/BgbWf3//sf37/1/c02cCG1lB8f//f95DZx74MTMzshhoSm6szrQ/a6Ir/Z2RkfEjBxuLYFpDiDi6Af///2ckaHBp7+7wmavP5n76+P2ClrLIYl8H9W36auJCbCxM4szMTJac7Kza////R3H1w2cfWAgafPbqs5g7D95++/P1B4+ECK8tAwMDw/1H7159+/7r7ZcvPz4fOHbzEwMDwx8GBgaGnNatfHZx8zqrJ+4VJBh5CQEGOySEua/v3n7hXmqI8WUGBgYGL3vVG7fuPK3i5GD9/fja7ZsMDAzMG/Ze52mZeSj4yu1XEq/ff7W5dvfVAS1lsXc4Db7z8C3r8p7Qjf///2dnZGxlqJuyr3rPqQd/Hhyu7oSpYWScylDQsd3kzvnH738wMDzj5GBN1VIWW4c3KDon7VOvm7S3paB9u5qsU5/x5KUnlY+eexQbkLNsErK61+++VnAJcfkyMTIwffj0QwZbJDKjcETs1Y8evyd48toz8y/ffzv//vPP4veffxpX77z6l5JewHPu8MqTDAwMDLzyrjb/mZm0JcT5Lj+89+Ybm6zz95oMh7s4XbygN3Sluq4Mj5K8iKMgP4f0////fv77//8nLy+7MCcXmyYDAwODS9jM9tcvPypd35pne3ljdjvj26+H2dhYpuENikgfvQeXNmSl3tqepxXsqhXPyc666s+fv1fMdKR3TK72zpix8nTc7bdfhfkEeVbC9KhbK/9iYWHiErbu6MWbY/7//8/4//9/pgOnH6jGVazvFDRtq2VgiBIZrUTIBgCk+ivHvuEKwAAAAABJRU5ErkJggg==">
        </i></div>
        <div data-action="ltr"  class="item">
        <i class="fa fa-ltr">
<svg viewBox="0 0 29.333333 29.333333" preserveAspectRatio="xMidYMid meet" height="22" width="22" focusable="false" aria-hidden="true"><path style="fill:#626262" d="m 17.666666,6.6666665 h -7.5 c -2.4999995,0 -4.4999995,2 -4.4999995,4.5000005 0,2.5 2,4.5 4.4999995,4.5 h 0.5 v 6 c 0,0.5 0.5,1 1,1 0.5,0 1,-0.5 1,-1 V 9.6666665 c 0,-0.5 0.5,-1 1,-1 0.5,0 1,0.5 1,1 V 21.666667 c 0,0.5 0.5,1 1,1 0.5,0 1,-0.5 1,-1 V 8.6666665 h 1 c 0.5,0 1,-0.5 1,-1 0,-0.5 -0.5,-1 -1,-1 z m 1,4.0000005 v 8 l 5,-4 z" /></svg>
        </i></div>
    </div>
</div>
<!--<div class="templates hidden">
    <div id="drop-font">
        <strong>Change Font</strong>
        <i class="fa fa-chevron-up quit"></i><br>
        Text Size: 
        <select id="textSelector">
            <option data-size="12">Small</option>
            <option data-size="24">Medium</option>
            <option data-size="30">Large</option>
        </select>
        <br>        Font: 
        <select id="fontSelect">
            <option data-fonts="georgia">Georgia</option>
            <option data-fonts="arial">Arial</option>
            <option data-fonts="helvetica, arial">Helvetica</option>
            <option data-fonts="menlo, consolas, courier new, monospace">Monospace</option>
            <option data-fonts=""Times New Roman", times">Times New Roman</option>
            <option data-fonts="tahoma, sans-serif">Tahoma</option>
            <option data-fonts=""Trebuchet MS"">Trebuchet MS</option>
            <option data-fonts="verdana">Verdana</option>
        </select><br>

        <div class="btn submitFont">Apply</div>
    </div>
    <div id="drop-link">
        <strong>Insert Link</strong>
        <i class="fa fa-chevron-up quit"></i>
        <input placeholder="Link URL" type="text" id="url" />
        <div class="btn submitLink">Insert</div>
    </div>
    <div id="drop-image">
        <strong>Insert Image</strong>
        <i class="fa fa-chevron-up quit"></i>
        <input placeholder="Image URL" type="text" id="imageUrl" />
        <div class="btn sumbitImageURL">Insert</div>
    </div>
</div>-->

`;
var ready = (callback) => {
    if (document.readyState != 'loading') callback();
    else document.addEventListener('DOMContentLoaded', callback);
}
ready(() => {
    SquireUI = function(options) {
        if (typeof options.buildPath == 'undefined') {
            options.buildPath = 'build/';
        }
        var div = document.createElement('div');
        div.className = 'Squire-UI';
        div.innerHTML = template;
        div.querySelectorAll('.item')
            .forEach(item => {
                item.addEventListener('click', (e) => {
                    var item = e.target.closest('div.item');
                    console.log('click on', e.target);
                    var iframe = document.querySelector('#squire-iframe');
                    var editor = iframe.contentWindow.editor;
                    var action = item.dataset.action;
                    console.log(action);
                    test = {
                        value: item.dataset.action,
                        testBold: editor.hasFormat('b'),
                        testItalic: editor.hasFormat('i'),
                        testUnderline: editor.hasFormat('u'),
                        testOrderedList: editor.hasFormat('u'),
                        testLink: editor.hasFormat('a'),
                        testQuote: editor.hasFormat('bold'),
                        isNotValue: function(a) {
                            return (a == action && this.value !== '');
                        }
                    };
                    editor.alignRight = function() {
                        editor.setTextAlignment('right');
                    };
                    editor.alignCenter = function() {
                        editor.setTextAlignment('center');
                    };
                    editor.alignLeft = function() {
                        editor.setTextAlignment('left');
                    };
                    editor.alignJustify = function() {
                        editor.setTextAlignment('justify');
                    };
                    editor.makeHeading = function() {
                        editor.setFontSize('2em');
                        editor.bold();
                    };
                    console.log('test', (test.testBold | test.testItalic | test.testUnderline | test.testOrderedList | test.testLink | test.testQuote));
                    console.log((action == 'italic' && test.testItalic));
                    if (action == 'bold') {
                        if (test.testBold) {
                            editor.removeBold();
                        } else {
                            editor.bold();
                        }
                    } else if (action == 'italic') {
                        if (test.testItalic) {
                            editor.removeItalic();
                        } else {
                            editor.italic();
                        }
                    } else if (action == 'underline') {
                        if (test.testUnderline) {
                            editor.removeUnderline();
                        } else {
                            editor.underline();
                        }
                    } else if (test.testLink) {
                        editor.removeLink();
                    } else if (test.testOrderedList) {
                        editor.removeList();
                    } else if (test.testQuote) {
                        editor.decreaseQuoteLevel();
                    } else if (test.isNotValue('makeLink') | test.isNotValue('insertImage') | test.isNotValue('selectFont')) {
                        // do nothing these are dropdowns.
                    } else {
                        editor.focus();
                    }
                })
            });
        var container, editor;
        if (options.replace) {
            var replaced = document.querySelector(options.replace);
            div.contents = replaced.innerHTML;
            container = replaced.parentNode;
            var iframe = document.querySelector('#squire-iframe');
            div.iframe = iframe;
            iframe.parentNode.insertBefore(div, iframe);
            var par = iframe.parentNode;
            par.insertBefore(div, iframe);
            par.style.display = 'flex';
            container.removeChild(par);
            container.insertBefore(par, replaced);
            container.removeChild(replaced);
        } else if (options.div) {
            container = document.querySelector(options.div);
        } else {
            throw new Error('No element was defined for the editor to inject to.');
        }
        return (div);
    };
});
