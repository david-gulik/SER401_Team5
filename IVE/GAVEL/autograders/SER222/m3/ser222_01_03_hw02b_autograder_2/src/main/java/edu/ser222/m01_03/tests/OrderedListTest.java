package edu.ser222.m01_03.tests;

import com.gradescope.jh61b.grader.GradedTest;
import edu.ser222.m01_03.*;
import org.junit.Test;

import java.util.ConcurrentModificationException;
import java.util.Iterator;
import java.util.NoSuchElementException;
import java.util.concurrent.ThreadLocalRandom;

import static org.junit.Assert.*;


public class OrderedListTest {

    public int getRandomInt(int max) {
        return ThreadLocalRandom.current().nextInt(0,  max+1);
    }

    ////////////////////////////////////////////////////////////////////////////////
    //public CompletedDoubleList() - a constructor [1 points]
    //@Test
    //@GradedTest(name="Constructor 1 [Hint: Default Constructor]", number="1.1", max_score=0)
    //public void testConstructor1() {
    //    ListADT<Integer> lst = new CompletedList<>();
    //}

    ////////////////////////////////////////////////////////////////////////////////
    //T removeFirst() throws NoSuchElementException; [3 points]

    @Test
    @GradedTest(name="removeFirst() 1 [Hint: Exception]", number="2.1", max_score=.5)
    //remove from empty, exception only.
    public void removeFirst1() {
        ListADT<Integer> lst = new CompletedList<>();

        assertThrows(NoSuchElementException.class, lst::removeFirst);
    }

    @Test
    @GradedTest(name="removeFirst() 2 [Hint: Basic Behavior with Add (one element)]", number="2.2", max_score=.5)
    //remove from one, check all state.
    public void removeFirst2() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();

        int element1 = getRandomInt(10);
        lst.add(element1);
        int result = lst.removeFirst();

        assertEquals("removeFirst() after operation(s) returned wrong value.", element1, result);
        assertProperlyEmptyList(lst);
    }

    //UTILITY

    private void assertState(OrderedListADT d, Object eleFirst, Object eleLast, int size, String TS) {
        assertEquals("first() after operation(s) returned wrong value.", eleFirst, d.first());
        assertEquals("last() after operation(s) returned wrong value.", eleLast, d.last());
        assertEquals("isEmpty() after operation(s) returned wrong value.", !(size > 0), d.isEmpty());
        assertEquals("size() after operation(s) returned wrong value.", size, d.size());
        assertEquals("toString() after operation(s) returned wrong value.", TS, d.toString().strip());
    }

    private void assertProperlyEmptyList(ListADT lst) {
        assertThrows("first() after attempting to empty deque did not throw exception.", NoSuchElementException.class, lst::first);
        assertThrows("last() after attempting to empty deque did not throw exception.", NoSuchElementException.class, lst::last);
        assertEquals("isEmpty() after attempting to empty deque returned wrong value.", true, lst.isEmpty());
        assertEquals("size() after attempting to empty deque returned wrong value.", 0, lst.size());
        assertEquals("toString() after operation(s) returned wrong value.", "empty", lst.toString().strip());
    }

    @Test
    @GradedTest(name="removeFirst() 3 [Hint: Basic Behavior with Add (multiple elements)]", number="2.3", max_score=.5)
    //remove from three to empty, check all state. 1+1pt
    public void removeFirst3() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();

        int element1 = getRandomInt(9);
        int element2 = getRandomInt(9) + 10; //target element
        int element3 = getRandomInt(9) + 20;
        lst.add(element1);
        lst.add(element2);
        lst.add(element3);
        lst.removeFirst();
        lst.removeFirst();
        int result = lst.removeFirst();

        assertEquals("removeFirst() after operation(s) returned wrong value.", element3, result);
        assertProperlyEmptyList(lst);
    }

    @Test
    @GradedTest(name="removeFirst() 4 [Hint: Basic Behavior with Add (multiple elements) + Accessors]", number="2.4", max_score=.5)
    //remove one from three. check all state.
    public void removeFirst4() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();

        int element1 = getRandomInt(9);
        int element2 = getRandomInt(9) + 10;
        int element3 = getRandomInt(9) + 20;
        lst.add(element3);
        lst.add(element1);
        lst.add(element2);

        int result = lst.removeFirst();

        assertEquals("removeFirst() after operation(s) returned wrong value.", element1, result);
        assertState(lst, Integer.valueOf(element2), Integer.valueOf(element3), 2, element2+" " + element3);
    }

    ////////////////////////////////////////////////////////////////////////////////
    //T removeLast() throws NoSuchElementException; 3 points

    @Test
    @GradedTest(name="removeLast() 1 [Hint: Exception]", number="3.1", max_score=.5)
    //remove from empty, exception only.
    public void removeLast1() {
        ListADT<Integer> lst = new CompletedList<>();

        assertThrows(NoSuchElementException.class, lst::removeLast);
    }

    @Test
    @GradedTest(name="removeLast() 2 [Hint: Basic Behavior with Add (one element)]", number="3.2", max_score=.5)
    //remove from one, check all state.
    public void removeLast2() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();

        int element1 = getRandomInt(9);
        lst.add(element1);
        int result = lst.removeLast();

        assertEquals("removeLast() after operation(s) returned wrong value.", element1, result);
        assertProperlyEmptyList(lst);
    }

    @Test
    @GradedTest(name="removeLast() 3 [Hint: Basic Behavior with Add (multiple elements)]", number="3.3", max_score=.5)
    //remove from three to empty, check all state. 1+1pt
    public void removeLast3() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();

        int element1 = getRandomInt(9);
        int element2 = getRandomInt(9) + 10;
        int element3 = getRandomInt(9) + 20;
        lst.add(element3);
        lst.add(element2);
        lst.add(element1);
        lst.removeFirst();
        lst.removeFirst();
        int result = lst.removeLast();

        assertEquals("removeLast() after operation(s) returned wrong value.", element3, result);
        assertProperlyEmptyList(lst);
    }

    @Test
    @GradedTest(name="removeLast() 4 [Hint: Basic Behavior with Add (multiple elements) + Accessors]", number="3.4", max_score=.5)
    //remove one from three. check all state. 1pt
    public void removeLast4() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        int element1 = getRandomInt(9);
        int element2 = getRandomInt(9) + 10;
        int element3 = getRandomInt(9) + 20;
        lst.add(element2);
        lst.add(element1);
        lst.add(element3);

        int result = lst.removeLast();

        assertEquals("removeFirst() after operation(s) returned wrong value.", element3, result);
        assertState(lst, Integer.valueOf(element1), Integer.valueOf(element2), 2, element1+" " + element2);
    }

    ////////////////////////////////////////////////////////////////////////////////
    //T remove(T element);

    //remove DNE from empty, assert empty
    @Test
    @GradedTest(name="remove() 1 [Hint: Exception]", number="4.1", max_score=.5)
    //remove from empty, exception only.
    public void remove1() {
        ListADT<Integer> lst = new CompletedList<>();

        assertThrows(NoSuchElementException.class, ()->{lst.remove(5);});
    }

    //remove DNE from many, check state
    @Test
    @GradedTest(name="remove() 2 [Hint: Exception, Invalid Element]", number="4.2", max_score=.5)
    public void remove2() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();

        int element1 = getRandomInt(9);
        int element2 = getRandomInt(9) + 10;
        int element3 = getRandomInt(9) + 20;
        int element4 = 334;
        lst.add(element3);
        lst.add(element1);
        lst.add(element2);
        lst.add(element4);

        assertThrows(NoSuchElementException.class, ()->{lst.remove(element4 + 30);});

        assertState(lst, Integer.valueOf(element1), Integer.valueOf(element4), 4, element1 + " " + element2 + " " + element3 + " " + element4);
    }

    //remove one from one, assert empty
    @Test
    @GradedTest(name="remove() 3 [Hint: Basic Behavior with Add (one element)]", number="4.3", max_score=.5)
    public void remove3() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();

        lst.add(89);
        int result = lst.remove(89);

        assertEquals("remove() after operation(s) returned wrong value.", 89, result);
        assertProperlyEmptyList(lst);
    }

    //remove one from many middle
    @Test
    @GradedTest(name="remove() 4 [Hint: Basic Behavior with Add (multiple elements)", number="4.4", max_score=.5)
    public void remove4() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();

        int element1 = getRandomInt(9);
        int element2 = getRandomInt(9) + 10;
        int element3 = getRandomInt(9) + 20;
        int element4 = 334;
        lst.add(element3);
        lst.add(element1);
        lst.add(element2);
        lst.add(element4);

        int result = lst.remove(element2);
        assertEquals("remove() after operation(s) returned wrong value.", element2, result);

        assertState(lst, Integer.valueOf(element1), Integer.valueOf(element4), 3, element1 + " " + element3 + " " + element4);
    }
    //remove one from many end 1
    @Test
    @GradedTest(name="remove() 5 [Hint: Generics]", number="4.5", max_score=1)
    public void remove5() {
        OrderedListADT<String> lst = new CompletedOrderedList<>();

        lst.add("C");
        lst.add("A");
        lst.add("B");
        lst.add("D");

        lst.remove("A");
        assertEquals("remove() after operation(s) returned wrong value.", "A", "A");

        assertState(lst, "B", "D", 3, "B C D");
    }

    ////////////////////////////////////////////////////////////////////////////////
    //T first() [1 points]
    @Test
    @GradedTest(name="first() 1 [Hint: Exception]", number="5.1", max_score=.5)
    public void testFirst1() {
        ListADT<Integer> lst = new CompletedList<>();

        assertThrows(NoSuchElementException.class, lst::first);
    }

    @Test
    @GradedTest(name="first() 2 [Hint: Basic Behavior with Add (one element)]", number="5.2", max_score=.5)
    public void testFirst2() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        int element1 = getRandomInt(9);
        lst.add(element1);

        assertEquals("first() after operation(s) returned wrong value.", new Integer(element1), lst.first());
    }

    ////////////////////////////////////////////////////////////////////////////////
    //T last() [1 points]
    @Test
    @GradedTest(name="last() 1 [Hint: Exception]", number="5.1", max_score=.5)
    public void testLast1() {
        ListADT<Integer> lst = new CompletedList<>();

        assertThrows(NoSuchElementException.class, lst::last);
    }

    @Test
    @GradedTest(name="last() 2 [Hint: Basic Behavior with Add (one element)]", number="6.2", max_score=.5)
    public void testLast2() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        int element1 = getRandomInt(9);
        lst.add(element1);

        assertEquals("last() after operation(s) returned wrong value.", new Integer(element1), lst.last());
    }

    ////////////////////////////////////////////////////////////////////////////////
    //boolean contains(T target); [3 points]

    //contains on empty list
    @Test
    @GradedTest(name="contains() 1 [Hint: Empty]", number="7.1", max_score=.5)
    public void testContains1() {
        ListADT<Integer> lst = new CompletedList<>();
        int element1 = getRandomInt(99);
        assertFalse(lst.contains(element1));
    }

    // add only (found)
    @Test
    @GradedTest(name="contains() 2 [Hint: Basic Behavior with Add (one element)]", number="7.2", max_score=.5)
    public void testContains2() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        int element1 = getRandomInt(9);
        lst.add(element1);
        assertTrue("contains() is not reporting that an element that was added is in the list.", lst.contains(element1));
    }

    // add only (not found)
    @Test
    @GradedTest(name="contains() 3 [Hint: Basic Behavior with Add (one element)]", number="7.3", max_score=.5)
    public void testContains3() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        int element1 = getRandomInt(9);
        lst.add(element1);
        assertFalse("contains() is reporting that element which doesn't exist is in list.", lst.contains(element1+5));
    }

    // add and removed others
    @Test
    @GradedTest(name="contains() 4 [Hint: Add and Remove (multiple elements)]", number="7.3", max_score=1)
    public void testContains4() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();

        int element1 = getRandomInt(9);
        int element2 = getRandomInt(9) + 10;
        int element3 = getRandomInt(9) + 20;
        lst.add(element2);
        lst.add(element1);
        lst.add(30);
        lst.add(element3);
        lst.remove(element1);
        lst.remove(element2);

        assertTrue(lst.contains(30)); // RA: for some reason, adding a comment breaks this.
    }

    // add and removed it
    @Test
    @GradedTest(name="contains() 5 [Hint: Add and Remove (multiple elements)]", number="7.4", max_score=.5)
    public void testContains5() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();

        lst.add(50);
        lst.add(1);
        lst.add(20);
        lst.add(16);
        lst.remove(50);
        lst.remove(1);
        lst.remove(20);
        lst.remove(16);
        assertFalse(lst.contains(20));
    }

    ////////////////////////////////////////////////////////////////////////////////
    //boolean isEmpty();
    @Test
    @GradedTest(name="isEmpty() 1 [Hint: Basic Behavior]", number="8.1", max_score=.5)
    public void testIsEmpty1() {
        ListADT<Integer> lst = new CompletedList<>();
        assertEquals("isEmpty() after operation(s) returned wrong value.", true, lst.isEmpty());
    }

    @Test
    @GradedTest(name="isEmpty() 2 [Hint: Basic Behavior]", number="8.2", max_score=.5)
    public void testIsEmpty2() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        lst.add(5);
        assertFalse(lst.isEmpty());
    }

    ////////////////////////////////////////////////////////////////////////////////
    //public int size() [1 points]
    @Test
    @GradedTest(name="size() 1 [Hint: Basic]", number="9.1", max_score=.5)
    public void testSize1() {
        ListADT<Integer> lst = new CompletedList<>();
        assertEquals(0, lst.size());

    }

    @Test
    @GradedTest(name="size() 2 [Hint: Basic Behavior with Add (one element)]", number="9.2", max_score=.5)
    public void testSize2() {
        //SolutionDoubleOrderedList
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        int element1 = getRandomInt(9);
        lst.add(element1);
        assertEquals("size() after attempting to empty deque returned wrong value.", 1, lst.size());
    }

    ////////////////////////////////////////////////////////////////////////////////
    //String toString(); [1 point]
    @Test
    @GradedTest(name="toString() 1 [Hint: Empty]", number="10.1", max_score=.5)
    public void testToString1() {
        ListADT<Integer> lst = new CompletedList<>();
        assertEquals("empty", lst.toString().strip());
    }

    @Test
    @GradedTest(name="toString() 2 [Hint: Basic Behavior with Add (multiple elements)]", number="10.2", max_score=.5)
    public void testToString2() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        int element1 = getRandomInt(9);
        int element2 = getRandomInt(9) + 10;
        int element3 = getRandomInt(9) + 20;
        lst.add(element1);
        lst.add(element3);
        lst.add(element2);
        assertEquals(element1 + " " + element2 + " " + element3, lst.toString().strip());
    }

    ////////////////////////////////////////////////////////////////////////////////
    //Iterator<T> iterator(); [6 points]

    @Test
    @GradedTest(name="iterator() 1 [Hint: Default Constructor]", number="11.1", max_score=.5)
    public void testIterator1() {
        ListADT<Integer> lst = new CompletedList<>();

        Iterator<Integer> iter = lst.iterator();
    }

    //data loop plain
    @Test
    @GradedTest(name="iterator() 2 [Hint: Basic Behavior]", number="11.2", max_score=1)
    public void testIterator2() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        int element1 = getRandomInt(4);
        int element2 = getRandomInt(9) + 10;
        int element3 = getRandomInt(9) + 20;
        int element4 = 334;

        lst.add(element2);
        lst.add(element1);
        lst.add(element4);
        lst.add(element3);

        Iterator<Integer> iter = lst.iterator();

        assertEquals(new Integer(element1), iter.next());
        assertEquals(new Integer(element2), iter.next());
        assertEquals(new Integer(element3), iter.next());
        assertEquals(new Integer(element4), iter.next());
    }

    @Test
    @GradedTest(name="iterator() 3 [Hint: Basic Behavior with Generics]", number="11.3", max_score=1)
    public void testIterator3() {
        OrderedListADT<String> lst = new CompletedOrderedList<>();
        lst.add("B");
        lst.add("A");
        lst.add("D");
        lst.add("C");

        Iterator<String> iter = lst.iterator();

        assertEquals("A", iter.next());
        assertEquals("B", iter.next());
        assertEquals("C", iter.next());
        assertEquals("D", iter.next());
    }

    //hasNext
    @Test
    @GradedTest(name="iterator() 4 [Hint: hasNext Basic Behavior]", number="11.4", max_score=.5)
    public void testIterator4() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();

        int element1 = getRandomInt(4);
        int element2 = getRandomInt(9) + 10;
        int element3 = getRandomInt(9) + 20;
        int element4 = 334;
        lst.add(element2);
        lst.add(element1);
        lst.add(element4);
        lst.add(element3);

        Iterator<Integer> iter = lst.iterator();

        assertTrue(iter.hasNext());
        assertEquals(new Integer(element1), iter.next());
        assertTrue(iter.hasNext());
        assertEquals(new Integer(element2), iter.next());
        assertTrue(iter.hasNext());
        assertEquals(new Integer(element3), iter.next());
        assertTrue(iter.hasNext());
        assertEquals(new Integer(element4), iter.next());
        assertFalse(iter.hasNext());
    }

    //hasNext ConcurrentModificationException 1
    @Test
    @GradedTest(name="iterator() 5 [Hint: hasNext Exception]", number="11.6", max_score=2)
    public void testIterator5() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();

        int element1 = getRandomInt(5);
        int element2 = getRandomInt(9) + 10;
        lst.add(element1);

        Iterator<Integer> iter = lst.iterator();
        lst.add(element2);
        lst.remove(element2);
        assertThrows(ConcurrentModificationException.class, iter::hasNext);
    }

    //next  .5
    @Test
    @GradedTest(name="iterator() 6 [Hint: Next Exception]", number="11.6", max_score=.5)
    public void testIterator6() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        int element1 = getRandomInt(5);
        lst.add(element1);

        Iterator<Integer> iter = lst.iterator();
        iter.next();
        assertThrows(NoSuchElementException.class, iter::next);
    }

    //remove
    @Test
    @GradedTest(name="iterator() 7 [Hint: Remove Exception]", number="11.7", max_score=.5)
    public void testIterator7() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        int element1 = getRandomInt(5);
        lst.add(element1);

        Iterator<Integer> iter = lst.iterator();

        assertThrows(UnsupportedOperationException.class, iter::remove);
    }

    ////////////////////////////////////////////////////////////////////////////////
    //void add(T element) [5 points]
    @Test
    @GradedTest(name="add() 1 [Hint: Basic Behavior]", number="12.1", max_score=1)
    //add to empty, minimal state checks.
    public void add1() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        int element1 = getRandomInt(9);
        lst.add(element1);
        assertEquals(new Integer(element1), lst.first());
    }

    @Test
    @GradedTest(name="add() 2 [Hint: Basic Behavior + Accessors]", number="12.2", max_score=1)
    //add to empty, check all state.
    public void add2() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        int element1 = getRandomInt(9);
        lst.add(element1);

        assertState(lst, new Integer(element1), new Integer(element1), 1, element1+"");
    }

    @Test
    @GradedTest(name="add() 3 [Hint: Basic Behavior + Accessors]", number="12.3", max_score=.5)
    //add to one, check all state.
    public void add3() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        lst.add(10);
        lst.add(8);

        assertState(lst, new Integer(8), new Integer(10), 2, "8 10");
    }

    @Test
    @GradedTest(name="add() 4 [Hint: Basic Behavior + Accessors]", number="12.4", max_score=.5)
    //add to one, check all state.
    public void add4() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        lst.add(5);
        lst.add(1);
        lst.add(10);
        lst.add(9);

        assertState(lst, new Integer(1), new Integer(10), 4, "1 5 9 10");
    }

    @Test
    @GradedTest(name="add() 6 [Hint: Generics + Accessors]", number="12.5", max_score=1)
    //add to one, check all state.
    public void add6() {
        OrderedListADT<String> lst = new CompletedOrderedList<>();
        lst.add("B");
        lst.add("A");

        assertState(lst, "A", "B", 2, "A B");
    }

    @Test
    @GradedTest(name="add() 5 [Hint: Null]", number="12.6", max_score=1)
    //add null to empty, check all state.
    public void add5() {
        OrderedListADT<Integer> lst = new CompletedOrderedList<>();
        lst.add(1);
        assertThrows(NullPointerException.class, ()->{lst.add(null);});
    }
}
